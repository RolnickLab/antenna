"""
Building a classifier-head training set out of what people verified in the UI.

Shared by the export management command and the training-data API so both agree on what
counts as a label and which rows land in the test split.
"""

import hashlib
import typing

from django.db.models import QuerySet

from ami.main.models import Identification, Project
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.embedding import DetectionEmbedding

DEFAULT_SPLIT_SALT = "antenna-head-v1"
DEFAULT_TEST_FRACTION = 0.2


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
    return "test" if (int(digest[:8], 16) / 0xFFFFFFFF) < test_fraction else "train"


def verified_occurrence_ids(project: Project) -> QuerySet:
    """Occurrences a person has identified and not taken back."""
    return (
        Identification.objects.filter(
            withdrawn=False,
            occurrence__project=project,
            occurrence__determination__isnull=False,
        )
        .order_by()
        .values_list("occurrence_id", flat=True)
        .distinct()
    )


def verified_training_rows(project: Project, algorithm: Algorithm) -> QuerySet[DetectionEmbedding]:
    """
    Embeddings whose detection sits under a verified occurrence.

    Constrained to one algorithm on purpose: vectors from different backbones are in
    different spaces and must never be mixed into one training set.
    """
    return (
        DetectionEmbedding.objects.filter(
            algorithm=algorithm,
            detection__occurrence_id__in=verified_occurrence_ids(project),
            detection__occurrence__determination__isnull=False,
        )
        .select_related("detection__occurrence__determination")
        .order_by("pk")
    )


def count_missing_embeddings(project: Project, algorithm: Algorithm) -> int:
    """Verified detections this algorithm has never embedded. They need a pipeline re-run."""
    from ami.main.models import Detection

    return (
        Detection.objects.filter(occurrence_id__in=verified_occurrence_ids(project))
        .exclude(embeddings__algorithm=algorithm)
        .count()
    )


def label_counts(project: Project, algorithm: Algorithm) -> dict[str, int]:
    """Verified crops per species, for the chosen algorithm."""
    from django.db.models import Count

    rows = (
        verified_training_rows(project, algorithm)
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
