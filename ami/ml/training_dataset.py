"""
Write a classifier-head training set to storage, for a processing service to collect.

The service is handed a URL rather than the rows themselves. A project with a few hundred
thousand verified labels is hundreds of megabytes; that is fragile to send in one request
and has to start over if the connection drops. A file in storage is small to hand over,
cheap to retry, and the service already downloads capture images from the same place.
"""

import json
import logging
import pathlib
import tempfile
import typing

import numpy as np
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.text import slugify

from ami.main.models import Project
from ami.ml import training_data
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.embedding import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

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
    split_salt: str = training_data.DEFAULT_SPLIT_SALT,
    test_fraction: float = training_data.DEFAULT_TEST_FRACTION,
    job_id: int | None = None,
) -> dict[str, typing.Any]:
    """
    Collect verified labels and their embeddings, and save them as one npz file.

    Returns the storage path, the URL a service can fetch, and the metadata describing
    what went in. Raises NotEnoughVerifiedData rather than writing a file nothing can be
    trained on.
    """
    counts = training_data.label_counts(project, algorithm)
    keep = training_data.species_with_enough_examples(counts, min_per_species)
    if not keep:
        raise NotEnoughVerifiedData(
            f"No species in '{project.name}' has at least {min_per_species} verified crops with an "
            f"embedding from {algorithm.key}. Verify more occurrences, or re-run the pipeline so the "
            "verified detections get embeddings."
        )

    classes = sorted(keep)
    class_index = {name: i for i, name in enumerate(classes)}

    rows = training_data.verified_training_rows(project, algorithm)
    total = rows.count()

    features = np.zeros((total, EMBEDDING_DIMENSIONS), dtype=DATASET_DTYPE)
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
        splits.append(training_data.split_for(occurrence.pk, split_salt, test_fraction))
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

    metadata = {
        "project": {"id": project.pk, "name": project.name},
        "algorithm": {"key": algorithm.key, "name": algorithm.name, "version": algorithm.version},
        "dimensions": EMBEDDING_DIMENSIONS,
        "dtype": np.dtype(DATASET_DTYPE).name,
        "classes": classes,
        "counts": {name: counts[name] for name in classes},
        "dropped_species": sorted(set(counts) - keep),
        "rows": kept,
        "train": n_train,
        "test": n_test,
        "verified_detections_without_embedding": training_data.count_missing_embeddings(project, algorithm),
        "settings": {
            "min_per_species": min_per_species,
            "split_salt": split_salt,
            "test_fraction": test_fraction,
            "split_grouped_by": "occurrence",
        },
    }

    file_path = _save(
        project=project,
        algorithm=algorithm,
        job_id=job_id,
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

    file_url = f"{settings.MEDIA_URL}{file_path}"
    logger.info(f"Wrote training dataset with {kept} rows over {len(classes)} species to {file_path}")
    return {"path": file_path, "url": file_url, "metadata": metadata}


def _save(
    project: Project,
    algorithm: Algorithm,
    job_id: int | None,
    arrays: dict[str, np.ndarray],
    metadata: dict[str, typing.Any],
) -> str:
    """
    Write the npz to storage and return its path.

    default_storage is the local filesystem in development and the project's S3 bucket in
    production, so this follows wherever captures already live without a special case.
    """
    stem = f"{slugify(project.name)}-{slugify(algorithm.key)}"
    suffix = f"job-{job_id}" if job_id else "manual"
    file_path = f"{DATASET_DIRECTORY}/{stem}-{suffix}.npz"

    with tempfile.TemporaryDirectory() as tmp:
        local = pathlib.Path(tmp) / "dataset.npz"
        # Uncompressed: embeddings are close to random, so compression buys about 10 per
        # cent for real CPU. Metadata rides inside the archive so the file is self-describing.
        np.savez(local, metadata=np.array(json.dumps(metadata)), **arrays)
        if default_storage.exists(file_path):
            # A re-run of the same job replaces its dataset instead of piling up copies.
            default_storage.delete(file_path)
        with open(local, "rb") as f:
            file_path = default_storage.save(file_path, f)

    return file_path
