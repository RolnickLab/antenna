"""Feature vectors for detections, read one algorithm at a time.

A detection's vector is stored in one of two places: a ``DetectionEmbedding`` row, which a
processing service can send for every detection, or the ``features_2048`` of one of its
classifications, which is all that data processed before embeddings existed has. Readers
take the embedding when there is one and otherwise the most recent classification vector
from the same algorithm. Vectors from different algorithms, or under different keys, are not
comparable, so every reader here is keyed by algorithm and key. A classification's vector is
the backbone ``embedding`` key. See #1417.
"""

from __future__ import annotations

import collections
import logging
from collections.abc import Iterable
from typing import Any

from django.db.models import Count, Exists, F, IntegerField, OuterRef, Q, QuerySet, Value
from django.db.models.functions import Cast
from pgvector.django import VectorField

logger = logging.getLogger(__name__)

DEFAULT_KEY = "embedding"
_PREFER_EMBEDDING = 0
_PREFER_CLASSIFICATION = 1


def _includes_classifications(key: str) -> bool:
    return key == DEFAULT_KEY


def _vector_rows(detection_ids: Iterable[int], algorithm_ids: Iterable[int] | None, key: str) -> QuerySet:
    """(detection_id, algorithm_id, vector, ...) rows from both stores in one query, preferred rows first."""
    from ami.main.models import Classification, DetectionEmbedding

    detection_ids = list(detection_ids)
    embeddings = DetectionEmbedding.objects.filter(detection_id__in=detection_ids, key=key)
    classifications = Classification.objects.filter(
        detection_id__in=detection_ids, algorithm_id__isnull=False, features_2048__isnull=False
    )
    if algorithm_ids is not None:
        algorithm_ids = list(algorithm_ids)
        embeddings = embeddings.filter(algorithm_id__in=algorithm_ids)
        classifications = classifications.filter(algorithm_id__in=algorithm_ids)

    # Model fields first, then the annotations in the same order, so both SELECT lists line up
    # column for column. The halfvec column is read as a vector so both sides share one type.
    # UNION ALL: de-duplicating would sort the vectors.
    embeddings = (
        embeddings.order_by()
        .annotate(
            vec=Cast("vector", VectorField()),
            preference=Value(_PREFER_EMBEDDING, output_field=IntegerField()),
            recorded_at=F("timestamp"),
        )
        .values_list("detection_id", "algorithm_id", "vec", "id", "preference", "recorded_at")
    )
    if not _includes_classifications(key):
        return embeddings.order_by("-recorded_at", "-id")
    classifications = (
        classifications.order_by()
        .annotate(
            vec=F("features_2048"),
            preference=Value(_PREFER_CLASSIFICATION, output_field=IntegerField()),
            recorded_at=F("timestamp"),
        )
        .values_list("detection_id", "algorithm_id", "vec", "id", "preference", "recorded_at")
    )
    return embeddings.union(classifications, all=True).order_by("preference", "-recorded_at", "-id")


def latest_vectors(
    detection_ids: Iterable[int], algorithm_ids: Iterable[int] | None = None, key: str = DEFAULT_KEY
) -> dict[tuple[int, int], Any]:
    """The vector under ``key`` for each (detection, algorithm) pair that has one, in one query.

    Pass ``algorithm_ids`` to read only those algorithms. The caller must still compare
    vectors from one algorithm only.
    """
    vectors: dict[tuple[int, int], Any] = {}
    for detection_id, algorithm_id, vector, *_ in _vector_rows(detection_ids, algorithm_ids, key):
        vectors.setdefault((detection_id, algorithm_id), vector)
    return vectors


def vectors_for_detections(detection_ids: Iterable[int], algorithm_id: int, key: str = DEFAULT_KEY) -> dict[int, Any]:
    """Each detection's vector from one (algorithm, key), in one query. Detections without one are absent.

    All the vectors returned have one length. Should an algorithm have stored two lengths
    (an embedding and an older classification vector), only the more common length is
    kept, so no caller can compare vectors of different sizes.
    """
    vectors = {
        detection_id: vector
        for (detection_id, _), vector in latest_vectors(detection_ids, [algorithm_id], key).items()
    }
    lengths = collections.Counter(len(vector) for vector in vectors.values())
    if len(lengths) > 1:
        keep = max(lengths, key=lambda length: (lengths[length], length))
        logger.warning(f"Algorithm {algorithm_id} has vectors of lengths {dict(lengths)}; using only length {keep}.")
        vectors = {detection_id: vector for detection_id, vector in vectors.items() if len(vector) == keep}
    return vectors


def algorithm_ids_with_vectors(key: str = DEFAULT_KEY, **detection_lookups: Any) -> set[int]:
    """Algorithms that stored a vector under ``key`` for any detection matching the lookups, in one query.

    Lookups are relative to the detection, e.g. ``source_image__event=event``.
    """
    from ami.main.models import Classification, DetectionEmbedding

    lookups = {f"detection__{name}": value for name, value in detection_lookups.items()}
    embedded = DetectionEmbedding.objects.filter(**lookups, key=key).order_by().values_list("algorithm_id", flat=True)
    if not _includes_classifications(key):
        return set(embedded)
    classified = (
        Classification.objects.filter(**lookups, features_2048__isnull=False, algorithm_id__isnull=False)
        .order_by()
        .values_list("algorithm_id", flat=True)
    )
    return set(embedded.union(classified))


# A configured extractor is preferred only once it covers nearly as many detections as the best
# one, so a feature-extraction run still in progress does not become the default for the session.
CONFIGURED_EXTRACTOR_MIN_COVERAGE = 0.9


def detections_covered(
    algorithm_ids: Iterable[int], key: str = DEFAULT_KEY, **detection_lookups: Any
) -> dict[int, int]:
    """How many detections matching the lookups have a vector under ``key`` from each algorithm, in one query.

    A detection counts once per algorithm whichever store (embedding or classification) holds its vector.
    """
    from ami.main.models import Classification, Detection, DetectionEmbedding

    algorithm_ids = list(algorithm_ids)
    if not algorithm_ids:
        return {}
    # The Exists terms are annotations, not a Q inside the Count, so cachalot sees their tables
    # and a newly stored vector invalidates the cached count.
    flags, counts = {}, {}
    for algorithm_id in algorithm_ids:
        embedded, classified = f"embedded_{algorithm_id}", f"classified_{algorithm_id}"
        flags[embedded] = Exists(
            DetectionEmbedding.objects.filter(detection_id=OuterRef("pk"), algorithm_id=algorithm_id, key=key)
        )
        has_vector = Q(**{embedded: True})
        if _includes_classifications(key):
            flags[classified] = Exists(
                Classification.objects.filter(
                    detection_id=OuterRef("pk"), algorithm_id=algorithm_id, features_2048__isnull=False
                )
            )
            has_vector |= Q(**{classified: True})
        counts[f"algorithm_{algorithm_id}"] = Count("pk", filter=has_vector)
    totals = Detection.objects.filter(**detection_lookups).order_by().annotate(**flags).aggregate(**counts)
    return {algorithm_id: totals[f"algorithm_{algorithm_id}"] for algorithm_id in algorithm_ids}


def default_feature_algorithm_id(project: Any, algorithm_ids: Iterable[int], **detection_lookups: Any) -> int | None:
    """The extractor to compare when the caller chose none, among ``algorithm_ids``.

    The one with vectors for the most detections matching the lookups, so the choice does not
    depend on which job wrote last. An extractor the project runs (a feature-extraction algorithm
    in a pipeline enabled for it) wins when it covers at least CONFIGURED_EXTRACTOR_MIN_COVERAGE
    of that. Ties go to the newest algorithm. At most 2 queries.
    """
    from ami.ml.models import Algorithm, Pipeline

    algorithm_ids = sorted(set(algorithm_ids))
    if len(algorithm_ids) <= 1:
        return algorithm_ids[0] if algorithm_ids else None
    configured = set(
        Algorithm.objects.filter(
            pk__in=algorithm_ids,
            task_type__in=Algorithm.feature_extraction_task_types,
            pipelines__in=Pipeline.objects.all().enabled(project).values("pk"),
        )
        .order_by()
        .values_list("pk", flat=True)
    )
    coverage = detections_covered(algorithm_ids, **detection_lookups)

    def rank(algorithm_id: int) -> tuple[int, int]:
        return coverage[algorithm_id], algorithm_id

    best = max(algorithm_ids, key=rank)
    eligible = [
        algorithm_id
        for algorithm_id in configured
        if coverage[algorithm_id] >= CONFIGURED_EXTRACTOR_MIN_COVERAGE * coverage[best]
    ]
    return max(eligible, key=rank) if eligible else best


def feature_extractors_with_vectors(project: Any, **detection_lookups: Any) -> list[dict[str, Any]]:
    """The algorithms with backbone vectors for the detections matching the lookups, and how many each has.

    Each row: the algorithm, ``embeddings_count`` (``DetectionEmbedding`` rows),
    ``classification_vectors_count`` (classifications carrying a vector) and ``is_default``,
    the one tracking compares when no extractor is chosen. Newest algorithm first. At most 5 queries.
    """
    from ami.main.models import Classification, DetectionEmbedding
    from ami.ml.models import Algorithm

    lookups = {f"detection__{name}": value for name, value in detection_lookups.items()}
    embedded = dict(
        DetectionEmbedding.objects.filter(**lookups, key=DEFAULT_KEY)
        .order_by()
        .values("algorithm_id")
        .annotate(n=Count("pk"))
        .values_list("algorithm_id", "n")
    )
    classified = dict(
        Classification.objects.filter(**lookups, features_2048__isnull=False, algorithm_id__isnull=False)
        .order_by()
        .values("algorithm_id")
        .annotate(n=Count("pk"))
        .values_list("algorithm_id", "n")
    )
    algorithm_ids = set(embedded) | set(classified)
    if not algorithm_ids:
        return []
    default_id = default_feature_algorithm_id(project, algorithm_ids, **detection_lookups)
    return [
        {
            "algorithm": algorithm,
            "embeddings_count": embedded.get(algorithm.pk, 0),
            "classification_vectors_count": classified.get(algorithm.pk, 0),
            "is_default": algorithm.pk == default_id,
        }
        for algorithm in Algorithm.objects.filter(pk__in=sorted(algorithm_ids)).order_by("-pk")
    ]
