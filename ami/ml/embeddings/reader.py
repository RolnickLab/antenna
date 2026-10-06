"""Feature vectors for detections, read one algorithm and key at a time.

Vectors from different algorithms, or under different keys of one algorithm, are not
comparable, so every reader here is keyed by algorithm and key. ``DetectionEmbedding`` holds
one row per (detection, algorithm, key). See #1462.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from django.db.models import Count

from ami.main.models import DEFAULT_EMBEDDING_KEY, Project
from ami.ml.models.embedding import DetectionEmbedding, as_half_precision


def vectors_for_detections(
    detection_ids: Iterable[int], algorithm_id: int, key: str = DEFAULT_EMBEDDING_KEY
) -> dict[int, np.ndarray]:
    """Each detection's vector from one (algorithm, key) as float32 arrays, in one query.

    Detections without one are absent. All the vectors have one length, because each
    algorithm keeps one (``Algorithm.embedding_dimensions``, checked on every write).
    """
    rows = (
        DetectionEmbedding.objects.for_algorithm(algorithm_id, key)
        .filter(detection_id__in=list(detection_ids))
        .order_by()
        .values_list("detection_id", "vector")
    )
    return {detection_id: as_half_precision(vector).astype(np.float32) for detection_id, vector in rows}


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
    """The algorithm that stored the most vectors under ``key`` in the project, or None when there are none."""
    return (
        DetectionEmbedding.objects.filter(project=project, key=key)
        .order_by()
        .values("algorithm_id")
        .annotate(n=Count("pk"))
        .order_by("-n", "algorithm_id")
        .values_list("algorithm_id", flat=True)
        .first()
    )
