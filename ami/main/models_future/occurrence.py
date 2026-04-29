"""
Reusable Prefetch factories for Occurrence list-view rendering.

Centralising these lets the queryset, serializer, and any future caller share
a single source of truth for what data the list view needs eagerly loaded.

Tracking issue: https://github.com/RolnickLab/antenna/issues/1271
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Prefetch

if TYPE_CHECKING:
    from ami.main.models import Classification, Identification, Occurrence


def prefetch_detections_for_list() -> Prefetch:
    """Single detections prefetch covering image URL listing AND best-prediction selection.

    One pass loads detections (ordered for stable image lists) plus their
    classifications with `taxon`/`algorithm` joined. The serializer derives
    image URLs by filtering `path is not None` in Python and picks the best
    machine prediction from the same cache.

    Replaces the previous pair (a `to_attr` filtered list for image paths
    plus a separate `detections__classifications` prefetch) which loaded the
    detections relation twice.
    """
    from ami.main.models import Classification, Detection

    return Prefetch(
        "detections",
        queryset=(
            Detection.objects.prefetch_related(
                Prefetch(
                    "classifications",
                    queryset=Classification.objects.select_related("taxon", "algorithm"),
                )
            ).order_by("frame_num", "timestamp")
        ),
    )


def prefetches_for_list_serializer() -> list[Prefetch]:
    """All prefetches `OccurrenceListSerializer` needs to render without N+1.

    Identifications are covered by `OccurrenceQuerySet.with_identifications()`
    which is already applied in the list viewset; intentionally not duplicated
    here.
    """
    return [prefetch_detections_for_list()]


def has_prefetched_classifications(occurrence: Occurrence) -> bool:
    """Return True iff `detections` AND each detection's `classifications` are prefetched.

    The list path prefetches both via `prefetch_detections_for_list()`. The
    detail path prefetches only `detections` — calling
    `best_prediction_from_prefetch()` there would walk `det.classifications.all()`
    and reintroduce an N+1 (one query per detection).
    """
    cache = getattr(occurrence, "_prefetched_objects_cache", {})
    detections = cache.get("detections")
    if detections is None:
        return False
    return all("classifications" in getattr(det, "_prefetched_objects_cache", {}) for det in detections)


def best_prediction_from_prefetch(occurrence: Occurrence) -> Classification | None:
    """Pick the best machine prediction from a prefetched occurrence in Python.

    Mirrors `Occurrence.best_prediction`, which calls `Occurrence.predictions()`
    (per-algorithm max-score filtering) and then orders by `-terminal, -score`.
    Replicating that grouping in Python keeps list and detail responses
    consistent for occurrences whose top-scoring classification is non-terminal.

    Requires `prefetch_detections_for_list()` (or equivalent) to have been
    applied; walks `obj.detections.all()` -> `det.classifications.all()` from
    the prefetch cache.
    """
    classifications = [c for det in occurrence.detections.all() for c in det.classifications.all()]
    if not classifications:
        return None

    max_score_per_algo: dict[object, float] = {}
    for c in classifications:
        score = c.score if c.score is not None else float("-inf")
        existing = max_score_per_algo.get(c.algorithm_id)
        if existing is None or score > existing:
            max_score_per_algo[c.algorithm_id] = score

    candidates = [
        c
        for c in classifications
        if (c.score if c.score is not None else float("-inf")) == max_score_per_algo[c.algorithm_id]
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda c: (
            0 if getattr(c, "terminal", False) else 1,
            -(c.score or 0.0),
            -c.pk,
        )
    )
    return candidates[0]


def best_identification_from_prefetch(occurrence: Occurrence) -> Identification | None:
    """Pick the most recent non-withdrawn identification from prefetched data.

    Mirrors `Occurrence.best_identification` (`order_by("-created_at")`), with
    a `pk` tiebreaker so equal timestamps produce a deterministic winner.
    `created_at=None` is treated as lower than any real timestamp.
    """
    best: Identification | None = None
    best_key: tuple[bool, object, int] | None = None
    for ident in occurrence.identifications.all():
        if ident.withdrawn:
            continue
        ident_key: tuple[bool, object, int] = (ident.created_at is not None, ident.created_at, ident.pk)
        if best_key is None or ident_key > best_key:
            best = ident
            best_key = ident_key
    return best


def detection_image_urls_from_prefetch(occurrence: Occurrence, limit: int | None = None) -> list[str]:
    """Return media URLs for the prefetched detections (filtering out `path=None`).

    Requires `prefetch_detections_for_list()` to have been applied.
    """
    from ami.main.models import get_media_url

    detections = [det for det in occurrence.detections.all() if det.path]
    if limit is not None:
        detections = detections[:limit]
    return [get_media_url(det.path) for det in detections]
