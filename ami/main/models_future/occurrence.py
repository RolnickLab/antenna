"""
Reusable Prefetch factories for Occurrence list/detail rendering.

The serializer trusts the prefetch contract — the viewset is the single place
that wires it up. Don't gate serializer methods on `_prefetched_objects_cache`
membership; require the prefetch.

Tracking issue: https://github.com/RolnickLab/antenna/issues/1271
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Prefetch

if TYPE_CHECKING:
    from ami.main.models import Classification, Identification, Occurrence


def _detections_prefetch(*, ordering: tuple[str, ...], with_source_image: bool) -> Prefetch:
    from ami.main.models import Classification, Detection

    qs = Detection.objects.prefetch_related(
        Prefetch(
            "classifications",
            queryset=Classification.objects.select_related("taxon", "algorithm"),
        )
    ).order_by(*ordering)
    if with_source_image:
        qs = qs.select_related("source_image")
    return Prefetch("detections", queryset=qs)


def prefetch_detections_for_list() -> Prefetch:
    """Detections + nested classifications, ordered for stable list image galleries."""
    return _detections_prefetch(ordering=("frame_num", "timestamp"), with_source_image=False)


def prefetch_detections_for_detail() -> Prefetch:
    """Detections + nested classifications + source_image, ordered most-recent-first.

    Detail responses serialize each detection via `DetectionNestedSerializer`,
    which dereferences `source_image` (as `capture`).
    """
    return _detections_prefetch(ordering=("-timestamp",), with_source_image=True)


def prefetches_for_list_serializer() -> list[Prefetch]:
    return [prefetch_detections_for_list()]


def prefetches_for_detail_serializer() -> list[Prefetch]:
    return [prefetch_detections_for_detail()]


def _require_prefetch(occurrence: Occurrence, *relations: str) -> None:
    """Raise if any required relation is missing from the prefetch cache.

    Strict contract: callers in serializer code must go through a viewset that
    applied the corresponding prefetch. Silent slow-pathing (the serializer
    triggering its own DB queries) is the N+1 we are fixing.

    Caveat: only top-level relations are checked. Nested prefetch (e.g.
    `detections__classifications`) is still required but not enforced here —
    if a caller prefetches `detections` without nested `classifications`,
    `best_prediction_from_prefetch` will silently re-introduce per-detection
    queries. The list/detail prefetch factories pair them correctly; new
    callers should use those factories rather than building Prefetch objects
    by hand. Tighter enforcement is deferred to the django-zen-queries pass
    (issue #1271 follow-up), which catches all per-row queries at the view
    boundary regardless of depth.
    """
    cache = getattr(occurrence, "_prefetched_objects_cache", {})
    missing = [r for r in relations if r not in cache]
    if missing:
        raise RuntimeError(
            f"Occurrence {occurrence.pk} is missing prefetched relations {missing!r}. "
            "Apply OccurrenceQuerySet.with_list_prefetches() / with_detail_prefetches() / "
            "with_identifications() in the viewset's get_queryset()."
        )


def best_prediction_from_prefetch(occurrence: Occurrence) -> Classification | None:
    """Pick the best machine prediction from a prefetched occurrence in Python.

    Mirrors `Occurrence.best_prediction`, which calls `Occurrence.predictions()`
    (per-algorithm max-score filtering) and then orders by `-terminal, -score`.

    Strict: requires `detections` (and each detection's `classifications`) to be
    prefetched. Raises if not.
    """
    _require_prefetch(occurrence, "detections")
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

    Mirrors `Occurrence.best_identification`, which uses
    `BEST_IDENTIFICATION_ORDER = ("-created_at", "-pk")`. `created_at=None` is
    treated as lower than any real timestamp.

    Strict: requires `identifications` to be prefetched (via
    `OccurrenceQuerySet.with_identifications()`).
    """
    _require_prefetch(occurrence, "identifications")
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

    Strict: requires `detections` to be prefetched. Pass `limit` to bound output —
    list responses cap at a few cover images; detail responses currently return
    all (TODO: bound when occurrence tracking lands; per-occurrence detection
    counts can reach thousands).
    """
    _require_prefetch(occurrence, "detections")

    from ami.main.models import get_media_url

    detections = [det for det in occurrence.detections.all() if det.path]
    if limit is not None:
        detections = detections[:limit]
    return [get_media_url(det.path) for det in detections]
