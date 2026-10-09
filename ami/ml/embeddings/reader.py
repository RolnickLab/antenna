"""Feature vectors for detections, read one algorithm and key at a time.

Vectors from different algorithms, or under different keys of one algorithm, are not
comparable, so every reader here is keyed by algorithm and key. ``DetectionEmbedding`` holds
one row per (detection, algorithm, key). Each function below serves one known query and says which
index it relies on. See #1462 and docs/claude/reference/feature-vectors.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

import numpy as np
from django.db.models import Count, Exists, OuterRef, QuerySet

from ami.main.models import Detection, Project
from ami.ml.embeddings import DEFAULT_EMBEDDING_KEY
from ami.ml.models.embedding import DetectionEmbedding, as_half_precision


def vectors_for_detections(
    detection_ids: Iterable[int], algorithm_id: int, key: str = DEFAULT_EMBEDDING_KEY
) -> dict[int, np.ndarray]:
    """The vectors of one (algorithm, key) for a set of detections, as float32 arrays, in one query.

    Serves "the vectors of one model for these detections" (two adjacent captures for tracking,
    verified detections for retraining) through the unique index on (detection, algorithm, key).
    Call it once per (algorithm, key); detections without a vector are absent. All the vectors
    have one length, because the writer holds each (algorithm, key) to one.
    """
    rows = (
        DetectionEmbedding.objects.for_algorithm(algorithm_id, key)
        .filter(detection_id__in=list(detection_ids))
        .order_by()
        .values_list("detection_id", "vector")
    )
    return {detection_id: as_half_precision(vector).astype(np.float32) for detection_id, vector in rows}


def project_vectors(
    project_id: int,
    algorithm_id: int,
    key: str = DEFAULT_EMBEDDING_KEY,
    *,
    detection_ids: Iterable[int] | None = None,
    chunk_size: int = 2000,
) -> Iterator[tuple[list[int], np.ndarray]]:
    """Every vector of one (algorithm, key) in a project, in chunks ordered by detection id.

    Serves exports, clustering and retraining sets that need all of a model's vectors without
    holding them all at once. Each chunk is (detection ids, float32 array of shape (n, length)).
    The next chunk is fetched with ``detection_id > last`` (keyset pagination), which walks the
    index on (project, algorithm, key, detection) in order, so memory stays at one chunk and no
    page re-reads earlier rows. ``detection_ids`` narrows the scope. Call it once per
    (algorithm, key): vectors of different models or lengths must not share an array.
    """
    scope = DetectionEmbedding.objects.for_algorithm(algorithm_id, key).filter(project_id=project_id)
    if detection_ids is not None:
        scope = scope.filter(detection_id__in=list(detection_ids))
    last_id = 0
    while True:
        rows = list(
            scope.filter(detection_id__gt=last_id)
            .order_by("detection_id")
            .values_list("detection_id", "vector")[:chunk_size]
        )
        if not rows:
            return
        last_id = rows[-1][0]
        yield (
            [detection_id for detection_id, _ in rows],
            np.stack([as_half_precision(vector).astype(np.float32) for _, vector in rows]),
        )


def vector_counts_by_algorithm(project_id: int, key: str | None = None) -> dict[tuple[int, str], int]:
    """How many vectors each (algorithm id, key) has in a project, in one grouped query.

    Serves "which models have vectors here" (the default model of a similarity sort, and any caller that
    must choose a model to compare). It reads only the (project, algorithm, key, detection) index. ``key``
    limits the result to one output name; the result is keyed by pair so nothing is merged across models.
    """
    rows = DetectionEmbedding.objects.filter(project_id=project_id)
    if key is not None:
        rows = rows.filter(key=key)
    grouped = rows.order_by().values_list("algorithm_id", "key").annotate(n=Count("pk"))
    return {(algorithm_id, row_key): n for algorithm_id, row_key, n in grouped}


def detections_missing_vectors(
    detections: QuerySet[Detection], algorithm_id: int, key: str = DEFAULT_EMBEDDING_KEY
) -> QuerySet[Detection]:
    """The given detections that have no vector yet from one (algorithm, key).

    Serves finding what a feature-extraction run still has to send. It adds a NOT EXISTS on the
    unique index (detection, algorithm, key) to the caller's queryset, so the caller keeps its
    own scope (project, capture set, station) and the filter adds no query of its own.
    """
    has_vector = DetectionEmbedding.objects.for_algorithm(algorithm_id, key).filter(detection_id=OuterRef("pk"))
    # exclude(), not filter(~Exists(...)): django-cachalot 2.6 does not see the tables inside a
    # negated Exists, so writes to the vector table would not invalidate a cached result.
    return detections.exclude(Exists(has_vector))


def representative_embeddings(occurrence_id, algorithm_id: int, key: str = DEFAULT_EMBEDDING_KEY):
    """One occurrence's vectors from one (algorithm, key), its representative detection's first.

    The representative detection is the earliest one that has such a vector, by frame number,
    then time, then id: the detection whose crop the occurrence list shows, when that crop has
    a vector. The seed of a similarity sort and every occurrence it ranks both go through this,
    so they are compared the same way. ``occurrence_id`` may be an ``OuterRef``.
    """
    return (
        DetectionEmbedding.objects.for_algorithm(algorithm_id, key)
        .filter(detection__occurrence_id=occurrence_id)
        .order_by("detection__frame_num", "detection__timestamp", "detection_id")
    )


def algorithm_with_most_vectors(project: Project, key: str = DEFAULT_EMBEDDING_KEY) -> int | None:
    """The algorithm that stored the most vectors under ``key`` in the project, or None when there are none.

    Ties go to the lowest algorithm id.
    """
    counts = vector_counts_by_algorithm(project.pk, key)
    if not counts:
        return None
    return min(counts, key=lambda pair: (-counts[pair], pair[0]))[0]
