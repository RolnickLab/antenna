"""
Build a classifier-head training set out of what people verified, and write it to storage.

Two halves of one job: deciding what counts as training data — which occurrences a person
identified, which species have enough of them, which rows are held out — and turning that
into a single file.

It is a file because a service is handed a URL, not the rows. A project with a few hundred
thousand verified labels runs to hundreds of megabytes, which is fragile to send in one
request and has to start over if the connection drops.
"""

import hashlib
import logging
import pathlib
import tempfile
import typing
from typing import TYPE_CHECKING

import numpy as np
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import QuerySet
from django.utils.text import slugify

from ami.main.models import DEFAULT_EMBEDDING_KEY, Identification, Project
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.embedding import DetectionEmbedding
from ami.ml.schemas import NamedReference, TrainedAlgorithmReference, TrainingDatasetMetadata, TrainingDatasetSettings

if TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.main.models import OccurrenceSet, TaxaList

logger = logging.getLogger(__name__)


DEFAULT_SPLIT_SALT = "antenna-head-v1"
DEFAULT_TEST_FRACTION = 0.2

# The two sides of the split. Named so the API, the dataset builder and the export
# cannot drift apart on spelling.
SPLIT_TRAIN = "train"
SPLIT_TEST = "test"
SPLITS = (SPLIT_TRAIN, SPLIT_TEST)


def split_for(
    occurrence_id: int,
    salt: str = DEFAULT_SPLIT_SALT,
    test_fraction: float = DEFAULT_TEST_FRACTION,
) -> str:
    """
    Assign an occurrence to "train" or "test", the same way every time.

    Grouped by occurrence, not detection: an occurrence is one insect across several
    frames, so a detection-level split puts near-identical crops on both sides and
    overstates accuracy. Hash-based, not random, so the test set does not move when new
    data arrives — an eval set that drifts cannot compare two heads.
    """
    digest = hashlib.sha256(f"{salt}:{occurrence_id}".encode()).hexdigest()
    return SPLIT_TEST if (int(digest[:8], 16) / 0xFFFFFFFF) < test_fraction else SPLIT_TRAIN


def verified_occurrence_ids(project: Project, occurrence_set: "OccurrenceSet | None" = None) -> QuerySet:
    """
    Occurrences a person has identified and not taken back.

    Narrowed to an occurrence set when one is given. A set is fixed once created, so a run
    that names one can be repeated and says for itself what it learned from; without one the
    pool is whatever happened to be verified that day, which no later reader can reconstruct.
    """
    identifications = Identification.objects.filter(
        withdrawn=False,
        occurrence__project=project,
        occurrence__determination__isnull=False,
    )
    if occurrence_set is not None:
        identifications = identifications.filter(occurrence__evaluation_sets=occurrence_set)
    return identifications.order_by().values_list("occurrence_id", flat=True).distinct()


def verified_training_rows(
    project: Project, algorithm: Algorithm, occurrence_set: "OccurrenceSet | None" = None
) -> QuerySet[DetectionEmbedding]:
    """
    Embeddings whose detection sits under a verified occurrence.

    Constrained to one algorithm on purpose: vectors from different backbones are in
    different spaces and must never be mixed into one training set.
    """
    return (
        DetectionEmbedding.objects.filter(
            algorithm=algorithm,
            key=DEFAULT_EMBEDDING_KEY,
            detection__occurrence_id__in=verified_occurrence_ids(project, occurrence_set),
            detection__occurrence__determination__isnull=False,
        )
        .select_related("detection__occurrence__determination")
        .order_by("pk")
    )


def count_missing_embeddings(
    project: Project, algorithm: Algorithm, occurrence_set: "OccurrenceSet | None" = None
) -> int:
    """Verified detections this algorithm has never embedded. They need a pipeline re-run."""
    from ami.main.models import Detection

    return (
        Detection.objects.filter(occurrence_id__in=verified_occurrence_ids(project))
        .exclude(embeddings__algorithm=algorithm)
        .count()
    )


def label_counts(
    project: Project, algorithm: Algorithm, occurrence_set: "OccurrenceSet | None" = None
) -> dict[str, int]:
    """Verified crops per species, for the chosen algorithm."""
    from django.db.models import Count

    rows = (
        verified_training_rows(project, algorithm, occurrence_set)
        .order_by()
        .values("detection__occurrence__determination__name")
        .annotate(n=Count("pk"))
    )
    return {r["detection__occurrence__determination__name"]: r["n"] for r in rows}


def species_with_enough_examples(counts: dict[str, int], minimum: int) -> set[str]:
    """A class with a single example cannot be both trained on and evaluated."""
    return {name for name, n in counts.items() if name and n >= minimum}


def row_as_dict(
    embedding: DetectionEmbedding,
    salt: str = DEFAULT_SPLIT_SALT,
    test_fraction: float = DEFAULT_TEST_FRACTION,
    include_features: bool = True,
) -> dict[str, typing.Any]:
    """One training row, in the shape the training-data API returns."""
    occurrence = embedding.detection.occurrence
    row = {
        "detection_id": embedding.detection_id,
        "occurrence_id": occurrence.pk if occurrence else None,
        "label": occurrence.determination.name if occurrence and occurrence.determination else None,
        "label_id": occurrence.determination_id if occurrence else None,
        "split": split_for(occurrence.pk, salt, test_fraction) if occurrence else None,
    }
    if include_features:
        row["features"] = embedding.vector.to_list()
    return row


# Vectors are written as float16 because that is exactly what Postgres stores (halfvec),
# so nothing is lost. Measured on 10k rows: npz float16 is 21 MB against 227 MB of JSON,
# and 1.1s to build against 29s.
DATASET_DTYPE = np.float16

DATASET_DIRECTORY = "training"

# Rows are pulled from the database in batches so a large project does not have to fit
# every vector in memory at once.
FETCH_BATCH_SIZE = 2000


class NotEnoughVerifiedData(Exception):
    """The project does not hold enough verified labels to train and evaluate on."""


def build_training_dataset(
    project: Project,
    algorithm: Algorithm,
    min_per_species: int = 2,
    split_salt: str = DEFAULT_SPLIT_SALT,
    test_fraction: float = DEFAULT_TEST_FRACTION,
    taxa_list: "TaxaList | None" = None,
    occurrence_set: "OccurrenceSet | None" = None,
    job: "Job | None" = None,
) -> dict[str, typing.Any]:
    """
    Collect verified labels and their embeddings, and save them as one npz file.

    Returns the storage path, the URL a service can fetch, and the metadata describing
    what went in. Raises NotEnoughVerifiedData rather than writing a file nothing can be
    trained on.
    """
    counts = label_counts(project, algorithm, occurrence_set)
    taxa_list = taxa_list or project.default_taxa_list

    if taxa_list:
        # The taxa list decides what the head can predict; the verified crops only decide
        # how well it predicts each one. Without this the head shrinks to whatever happened
        # to be verified, which silently narrows the pipeline.
        classes = sorted(taxa_list.taxa.exclude(name="").values_list("name", flat=True))
        if not classes:
            raise NotEnoughVerifiedData(f"Taxa list '{taxa_list}' is empty, so there is nothing to train.")
        keep = set(classes)
        outside = sorted(name for name in counts if name and name not in keep)
    else:
        keep = species_with_enough_examples(counts, min_per_species)
        if not keep:
            raise NotEnoughVerifiedData(
                f"No species in '{project.name}' has at least {min_per_species} verified crops with an "
                f"embedding from {algorithm.key}. Verify more occurrences, or re-run the pipeline so the "
                "verified detections get embeddings."
            )
        classes = sorted(keep)
        outside = sorted(set(counts) - keep)

    class_index = {name: i for i, name in enumerate(classes)}

    rows = verified_training_rows(project, algorithm, occurrence_set)
    total = rows.count()

    # Asked rather than assumed: a vector's width belongs to the model that produced it, and
    # the column is unsized so two algorithms may differ.
    dimensions = DetectionEmbedding.objects.stored_length(algorithm.pk)
    if dimensions is None:
        raise NotEnoughVerifiedData(
            f"No detection has a feature vector from '{algorithm.key}' yet, so there is nothing to train on."
        )
    features = np.zeros((total, dimensions), dtype=DATASET_DTYPE)
    labels = np.zeros(total, dtype=np.int64)
    detection_ids = np.zeros(total, dtype=np.int64)
    occurrence_ids = np.zeros(total, dtype=np.int64)
    splits: list[str] = []

    kept = 0
    for embedding in rows.iterator(chunk_size=FETCH_BATCH_SIZE):
        occurrence = embedding.detection.occurrence
        if not occurrence or not occurrence.determination:
            continue
        name = occurrence.determination.name
        if name not in class_index:
            continue
        features[kept] = np.asarray(embedding.vector.to_list(), dtype=DATASET_DTYPE)
        labels[kept] = class_index[name]
        detection_ids[kept] = embedding.detection_id
        occurrence_ids[kept] = occurrence.pk
        splits.append(split_for(occurrence.pk, split_salt, test_fraction))
        kept += 1

    if not kept:
        raise NotEnoughVerifiedData("No verified detection has an embedding from this algorithm yet.")

    features = features[:kept]
    labels = labels[:kept]
    detection_ids = detection_ids[:kept]
    occurrence_ids = occurrence_ids[:kept]
    split_array = np.array(splits)

    n_train = int((split_array == "train").sum())
    n_test = int((split_array == "test").sum())
    if not n_train or not n_test:
        raise NotEnoughVerifiedData(
            f"The split left {n_train} training and {n_test} held-out rows. Both sides need rows "
            "before a new head can be compared against the current one."
        )

    file_path = dataset_path(project, algorithm, job.pk if job else None)
    # Declared, not assembled: the shape is checked here rather than at each reader, and
    # the service echoes it back in its result.
    metadata = TrainingDatasetMetadata(
        url=f"{settings.MEDIA_URL}{file_path}",
        project=NamedReference(id=project.pk, name=project.name),
        algorithm=TrainedAlgorithmReference(key=algorithm.key, name=algorithm.name, version=algorithm.version),
        dimensions=dimensions,
        dtype=np.dtype(DATASET_DTYPE).name,
        classes=classes,
        # .get(): with a taxa list, a class can legitimately have no verified crops yet.
        counts={name: counts.get(name, 0) for name in classes},
        taxa_list=NamedReference(id=taxa_list.pk, name=taxa_list.name) if taxa_list else None,
        occurrence_set=(NamedReference(id=occurrence_set.pk, name=occurrence_set.name) if occurrence_set else None),
        classes_without_verified_data=sorted(name for name in classes if not counts.get(name)),
        dropped_species=outside,
        rows=kept,
        train=n_train,
        test=n_test,
        verified_detections_without_embedding=count_missing_embeddings(project, algorithm, occurrence_set),
        settings=TrainingDatasetSettings(
            min_per_species=min_per_species,
            split_salt=split_salt,
            test_fraction=test_fraction,
        ),
    )

    file_path = _save(
        file_path=file_path,
        arrays={
            "features": features,
            "labels": labels,
            "detection_ids": detection_ids,
            "occurrence_ids": occurrence_ids,
            "split": split_array,
            "classes": np.array(classes),
        },
        metadata=metadata,
    )

    file_url = metadata.url
    logger.info(f"Wrote training dataset with {kept} rows over {len(classes)} species to {file_path}")
    return {"path": file_path, "url": file_url, "metadata": metadata}


def dataset_path(project: Project, algorithm: Algorithm, job_id: int | None) -> str:
    """Where this project's training set for this algorithm is written."""
    stem = f"{slugify(project.name)}-{slugify(algorithm.key)}"
    suffix = f"job-{job_id}" if job_id else "manual"
    return f"{DATASET_DIRECTORY}/{stem}-{suffix}.npz"


def _save(
    file_path: str,
    arrays: dict[str, np.ndarray],
    metadata: TrainingDatasetMetadata,
) -> str:
    """
    Write the npz to storage and return its path.

    default_storage is the local filesystem in development and the project's S3 bucket in
    production, so this follows wherever captures already live without a special case.
    """
    with tempfile.TemporaryDirectory() as tmp:
        local = pathlib.Path(tmp) / "dataset.npz"
        # Uncompressed: embeddings are close to random, so compression buys about 10 per
        # cent for real CPU. Metadata rides inside the archive so the file is self-describing.
        np.savez(local, metadata=np.array(metadata.json()), **arrays)
        if default_storage.exists(file_path):
            # A re-run of the same job replaces its dataset instead of piling up copies.
            default_storage.delete(file_path)
        with open(local, "rb") as f:
            saved_path = default_storage.save(file_path, f)

    if saved_path != file_path:
        # The metadata inside the archive records the URL it was written to, so a rename
        # by the storage backend would leave the file describing somewhere it is not.
        logger.warning(f"Storage wrote the training set to {saved_path}, not {file_path}.")
    return saved_path
