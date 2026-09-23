"""Feature vectors for detections, read one algorithm at a time.

A detection's vector is stored in one of two places: a ``DetectionEmbedding`` row, which a
processing service can send for every detection, or the ``features_2048`` of one of its
classifications, which is all that data processed before embeddings existed has. Readers
take the embedding when there is one and otherwise the most recent classification vector
from the same algorithm. Vectors from different algorithms are not comparable, so every
reader here is keyed by algorithm. See #1417.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.db.models import F, IntegerField, QuerySet, Value

_PREFER_EMBEDDING = 0
_PREFER_CLASSIFICATION = 1


def _vector_rows(detection_ids: Iterable[int], algorithm_ids: Iterable[int] | None) -> QuerySet:
    """(detection_id, algorithm_id, vector, ...) rows from both stores in one query, preferred rows first."""
    from ami.main.models import Classification, DetectionEmbedding

    detection_ids = list(detection_ids)
    embeddings = DetectionEmbedding.objects.filter(detection_id__in=detection_ids)
    classifications = Classification.objects.filter(
        detection_id__in=detection_ids, algorithm_id__isnull=False, features_2048__isnull=False
    )
    if algorithm_ids is not None:
        algorithm_ids = list(algorithm_ids)
        embeddings = embeddings.filter(algorithm_id__in=algorithm_ids)
        classifications = classifications.filter(algorithm_id__in=algorithm_ids)

    # Model fields first, then the annotations in the same order, so both SELECT lists line up
    # column for column (the vector columns differ in name). UNION ALL: de-duplicating would sort the vectors.
    embeddings = (
        embeddings.order_by()
        .annotate(preference=Value(_PREFER_EMBEDDING, output_field=IntegerField()), recorded_at=F("updated_at"))
        .values_list("detection_id", "algorithm_id", "vector", "id", "preference", "recorded_at")
    )
    classifications = (
        classifications.order_by()
        .annotate(preference=Value(_PREFER_CLASSIFICATION, output_field=IntegerField()), recorded_at=F("timestamp"))
        .values_list("detection_id", "algorithm_id", "features_2048", "id", "preference", "recorded_at")
    )
    return embeddings.union(classifications, all=True).order_by("preference", "-recorded_at", "-id")


def latest_vectors(
    detection_ids: Iterable[int], algorithm_ids: Iterable[int] | None = None
) -> dict[tuple[int, int], Any]:
    """The vector for each (detection, algorithm) pair that has one, in one query.

    Pass ``algorithm_ids`` to read only those algorithms. The caller must still compare
    vectors from one algorithm only.
    """
    vectors: dict[tuple[int, int], Any] = {}
    for detection_id, algorithm_id, vector, *_ in _vector_rows(detection_ids, algorithm_ids):
        vectors.setdefault((detection_id, algorithm_id), vector)
    return vectors


def vectors_for_detections(detection_ids: Iterable[int], algorithm_id: int) -> dict[int, Any]:
    """Each detection's vector from one algorithm, in one query. Detections without one are absent."""
    return {
        detection_id: vector for (detection_id, _), vector in latest_vectors(detection_ids, [algorithm_id]).items()
    }


def algorithm_ids_with_vectors(**detection_lookups: Any) -> set[int]:
    """Algorithms that stored a vector for any detection matching the lookups, in one query.

    Lookups are relative to the detection, e.g. ``source_image__event=event``.
    """
    from ami.main.models import Classification, DetectionEmbedding

    lookups = {f"detection__{key}": value for key, value in detection_lookups.items()}
    embedded = DetectionEmbedding.objects.filter(**lookups).order_by().values_list("algorithm_id", flat=True)
    classified = (
        Classification.objects.filter(**lookups, features_2048__isnull=False, algorithm_id__isnull=False)
        .order_by()
        .values_list("algorithm_id", flat=True)
    )
    return set(embedded.union(classified))
