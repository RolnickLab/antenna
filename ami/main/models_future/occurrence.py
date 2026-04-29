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


def prefetch_detection_images() -> Prefetch:
    """Detections with non-null `path`, ordered for stable image lists.

    Populates `Occurrence.prefetched_detection_images` so the serializer can
    yield image URLs without a per-occurrence query.
    """
    from ami.main.models import Detection

    return Prefetch(
        "detections",
        queryset=(
            Detection.objects.exclude(path=None)
            .only("id", "occurrence_id", "path", "frame_num", "timestamp")
            .order_by("frame_num", "timestamp")
        ),
        to_attr="prefetched_detection_images",
    )


def prefetch_classifications_for_best_prediction() -> Prefetch:
    """All classifications under each occurrence's detections.

    `taxon` and `algorithm` are joined so picking the best prediction in
    Python (via BEST_MACHINE_PREDICTION_ORDER) does not lazy-load either.

    The default `detections` relation manager populates `obj.detections.all()`
    which the caller can walk to reach `.classifications.all()`.
    """
    from ami.main.models import Classification

    return Prefetch(
        "detections__classifications",
        queryset=Classification.objects.select_related("taxon", "algorithm"),
    )


def prefetches_for_list_serializer() -> list[Prefetch]:
    """All prefetches `OccurrenceListSerializer` needs to render without N+1.

    Identifications are covered by `OccurrenceQuerySet.with_identifications()`
    which is already applied in the list viewset; intentionally not duplicated
    here.
    """
    return [
        prefetch_detection_images(),
        prefetch_classifications_for_best_prediction(),
    ]


def best_prediction_from_prefetch(occurrence: Occurrence) -> Classification | None:
    """Pick the best machine prediction from a prefetched occurrence in Python.

    Mirrors the ordering used by `BEST_MACHINE_PREDICTION_ORDER`
    (`-terminal`, `-score`, `-pk`).

    Requires `prefetch_classifications_for_best_prediction()` to have been
    applied; walks `obj.detections.all()` -> `det.classifications.all()` from
    the prefetch cache.
    """
    classifications: list = []
    for det in occurrence.detections.all():
        classifications.extend(det.classifications.all())
    if not classifications:
        return None
    classifications.sort(
        key=lambda c: (
            0 if getattr(c, "terminal", False) else 1,
            -(c.score or 0.0),
            -c.pk,
        )
    )
    return classifications[0]


def best_identification_from_prefetch(occurrence: Occurrence) -> Identification | None:
    """Pick the most recent non-withdrawn identification from prefetched data.

    Mirrors `Occurrence.best_identification` but reads from the prefetched
    `identifications` relation rather than issuing a fresh query.
    """
    best: Identification | None = None
    for ident in occurrence.identifications.all():
        if ident.withdrawn:
            continue
        if best is None or (ident.created_at and best.created_at and ident.created_at > best.created_at):
            best = ident
    return best


def detection_image_urls_from_prefetch(occurrence: Occurrence, limit: int | None = None) -> list[str]:
    """Return media URLs from the `prefetched_detection_images` to_attr list.

    Requires `prefetch_detection_images()` to have been applied.
    """
    from ami.main.models import get_media_url

    detections = getattr(occurrence, "prefetched_detection_images", [])
    if limit is not None:
        detections = detections[:limit]
    return [get_media_url(det.path) for det in detections]
