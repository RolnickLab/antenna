"""Feature vectors for detections, read one algorithm at a time.

Vectors from different algorithms are not comparable, so every reader here takes one algorithm.
``DetectionEmbedding`` holds one row per (detection, algorithm). Each function below serves one known
query and says which index it relies on. See #1462 and docs/claude/reference/feature-vectors.md.
"""

from __future__ import annotations

from django.db.models import Count

from ami.main.models import Project
from ami.ml.models.embedding import DetectionEmbedding


def vector_counts_by_algorithm(project_id: int) -> dict[int, int]:
    """How many vectors each algorithm has in a project, keyed by algorithm id, in one grouped query.

    Serves "which models have vectors here" (the default model of a similarity sort, and any caller that
    must choose a model to compare). It reads only the (project, algorithm, detection) index.
    """
    grouped = (
        DetectionEmbedding.objects.filter(project_id=project_id)
        .order_by()
        .values_list("algorithm_id")
        .annotate(n=Count("pk"))
    )
    return dict(grouped)


def representative_embeddings(occurrence_id, algorithm_id: int):
    """One occurrence's vectors from one algorithm, its representative detection's first.

    The representative detection is the earliest one that has such a vector, by frame number,
    then time, then id: the detection whose crop the occurrence list shows, when that crop has
    a vector. The seed of a similarity sort and every occurrence it ranks both go through this,
    so they are compared the same way. ``occurrence_id`` may be an ``OuterRef``.
    """
    return (
        DetectionEmbedding.objects.for_algorithm(algorithm_id)
        .filter(detection__occurrence_id=occurrence_id)
        .order_by("detection__frame_num", "detection__timestamp", "detection_id")
    )


def algorithm_with_most_vectors(project: Project) -> int | None:
    """The algorithm that stored the most vectors in the project, or None when there are none.

    Ties go to the lowest algorithm id.
    """
    counts = vector_counts_by_algorithm(project.pk)
    if not counts:
        return None
    return min(counts, key=lambda algorithm_id: (-counts[algorithm_id], algorithm_id))
