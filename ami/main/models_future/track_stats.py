"""Per-occurrence track statistics: how far a tracked insect moved, how much its box
changed, and how consistently it was labelled.

One set of definitions, two homes. Four of the numbers are stored on the occurrence row
(``Occurrence.track_*``) so the list endpoint can sort by them; ``refresh_track_stats``
recomputes them in SQL whenever tracking or a track edit changes which detections an
occurrence holds, and ``backfill_track_stats`` fills in rows from before the fields
existed. The detail endpoint computes the same numbers live, in Python, from the
detections it has already prefetched, so its card always describes the current row.

Definitions:
- ``frames``: detections in the occurrence.
- ``motion``: path length between consecutive detection centres, ordered by
  (timestamp, id), divided by the frame diagonal. A stationary insect scores ~0.
- ``size_ratio``: largest bbox area over smallest, areas floored at 1.0.
- ``distinct_taxa``: distinct taxa among terminal classifications, across every
  algorithm, so two classifiers that disagree count as two taxa.
- ``id_agreement``: share of terminal classifications naming the determination;
  null when there are none.

The frame diagonal is taken from the largest capture width and height seen; when the
captures carry no dimensions it falls back to the farthest bbox corner, and to 1.0 when
that is also unknown. Stats are returned for single-detection occurrences as well
(motion 0.0, size_ratio 1.0), so the payload has one shape.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.db import connection

if TYPE_CHECKING:
    from ami.main.models import Detection, Occurrence

TRACK_STATS_KEYS = ("frames", "motion", "size_ratio", "distinct_taxa", "id_agreement")

# The stored subset, in the order the Occurrence fields are declared. ``frames`` is not
# stored: the list already annotates ``detections_count``.
TRACK_STAT_FIELDS = ("track_motion", "track_size_ratio", "track_distinct_taxa", "track_id_agreement")

# Ids per statement when refreshing many rows; keeps the ``ANY(%s)`` arrays and the
# CASE expression ``bulk_update`` builds to a size Postgres plans quickly.
REFRESH_BATCH_SIZE = 500

_MIN_AREA = 1.0
_ROUND_TO = 4


def frame_diagonal(
    max_width: float | None, max_height: float | None, max_x2: float | None, max_y2: float | None
) -> float:
    """Length motion is normalised by, in the same pixel units as the bboxes."""
    if max_width and max_height:
        return math.hypot(max_width, max_height)
    if max_x2 or max_y2:
        return math.hypot(max_x2 or 0.0, max_y2 or 0.0) or 1.0
    return 1.0


def size_ratio(min_area: float | None, max_area: float | None) -> float:
    if not min_area or not max_area:
        return 1.0
    return round(max_area / min_area, _ROUND_TO)


def id_agreement(agreeing: int, terminal_count: int) -> float | None:
    if terminal_count == 0:
        return None
    return round(agreeing / terminal_count, _ROUND_TO)


def bbox_corners(bbox) -> tuple[float, float, float, float] | None:
    if not bbox or len(bbox) < 4:
        return None
    try:
        return tuple(float(v) for v in bbox[:4])  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _detection_order_key(detection: Detection) -> tuple:
    # Same order as the SQL window: timestamp ascending, nulls last, then id. A None
    # timestamp is never compared against a datetime because the leading flag differs.
    return (detection.timestamp is None, detection.timestamp, detection.pk)


def _geometry_from_detections(detections: list[Detection]) -> tuple[float, float]:
    """(motion, size_ratio) over detections that are already sorted into track order."""
    path_length = 0.0
    prev_centre: tuple[float, float] | None = None
    min_area: float | None = None
    max_area: float | None = None
    max_width: int | None = None
    max_height: int | None = None
    max_x2: float | None = None
    max_y2: float | None = None

    for detection in detections:
        corners = bbox_corners(detection.bbox)
        if corners is None:
            prev_centre = None
            continue
        x1, y1, x2, y2 = corners
        centre = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        if prev_centre is not None:
            path_length += math.dist(prev_centre, centre)
        prev_centre = centre

        area = max(abs((x2 - x1) * (y2 - y1)), _MIN_AREA)
        min_area = area if min_area is None else min(min_area, area)
        max_area = area if max_area is None else max(max_area, area)
        max_x2 = x2 if max_x2 is None else max(max_x2, x2)
        max_y2 = y2 if max_y2 is None else max(max_y2, y2)

        source_image = getattr(detection, "source_image", None)
        if source_image is not None:
            if source_image.width:
                max_width = max(max_width or 0, source_image.width)
            if source_image.height:
                max_height = max(max_height or 0, source_image.height)

    diagonal = frame_diagonal(max_width, max_height, max_x2, max_y2)
    return round(path_length / diagonal, _ROUND_TO), size_ratio(min_area, max_area)


def _classification_stats(
    terminal_taxon_ids: Iterable[int | None], determination_id: int | None
) -> tuple[int, float | None]:
    """(distinct_taxa, id_agreement). A classification with no taxon never agrees."""
    taxon_ids = list(terminal_taxon_ids)
    distinct = len({taxon_id for taxon_id in taxon_ids if taxon_id is not None})
    agreeing = sum(1 for taxon_id in taxon_ids if taxon_id is not None and taxon_id == determination_id)
    return distinct, id_agreement(agreeing, len(taxon_ids))


def track_stats_from_detections(detections: Iterable[Detection], determination_id: int | None) -> dict:
    """The list-endpoint stats, computed in Python from prefetched detections.

    Each detection's ``classifications`` must be prefetched and ``source_image``
    select_related, or this issues a query per detection.
    """
    ordered = sorted(detections, key=_detection_order_key)
    motion, ratio = _geometry_from_detections(ordered)
    terminal_taxon_ids = [c.taxon_id for d in ordered for c in d.classifications.all() if c.terminal]
    distinct, agreement = _classification_stats(terminal_taxon_ids, determination_id)
    return {
        "frames": len(ordered),
        "motion": motion,
        "size_ratio": ratio,
        "distinct_taxa": distinct,
        "id_agreement": agreement,
    }


# One row per occurrence: frame count, summed centre-to-centre distance in track order,
# and the extremes the diagonal and size ratio are derived from. The CASE keeps a
# detection without a bbox out of the area extremes instead of flooring it to 1.0.
_GEOMETRY_SQL = """
WITH frames AS (
    SELECT
        d.occurrence_id,
        d.id,
        d.timestamp,
        (d.bbox->>0)::float AS x1,
        (d.bbox->>1)::float AS y1,
        (d.bbox->>2)::float AS x2,
        (d.bbox->>3)::float AS y2,
        si.width,
        si.height
    FROM {detection} d
    LEFT JOIN {source_image} si ON si.id = d.source_image_id
    WHERE d.occurrence_id = ANY(%s)
),
steps AS (
    SELECT
        occurrence_id,
        (x1 + x2) / 2.0 AS cx,
        (y1 + y2) / 2.0 AS cy,
        LAG((x1 + x2) / 2.0) OVER track AS prev_cx,
        LAG((y1 + y2) / 2.0) OVER track AS prev_cy,
        CASE WHEN x1 IS NULL THEN NULL ELSE GREATEST(ABS((x2 - x1) * (y2 - y1)), {min_area}) END AS area,
        x2,
        y2,
        width,
        height
    FROM frames
    WINDOW track AS (PARTITION BY occurrence_id ORDER BY timestamp, id)
)
SELECT
    occurrence_id,
    COUNT(*) AS frames,
    COALESCE(SUM(SQRT(POWER(cx - prev_cx, 2) + POWER(cy - prev_cy, 2))), 0.0) AS path_length,
    MIN(area) AS min_area,
    MAX(area) AS max_area,
    MAX(width) AS max_width,
    MAX(height) AS max_height,
    MAX(x2) AS max_x2,
    MAX(y2) AS max_y2
FROM steps
GROUP BY occurrence_id
"""

# One row per occurrence that has terminal classifications.
_CLASSIFICATION_SQL = """
SELECT
    d.occurrence_id,
    COUNT(DISTINCT c.taxon_id) AS distinct_taxa,
    COUNT(*) AS terminal_count,
    COUNT(*) FILTER (WHERE c.taxon_id = o.determination_id) AS agreeing
FROM {classification} c
JOIN {detection} d ON d.id = c.detection_id
JOIN {occurrence} o ON o.id = d.occurrence_id
WHERE d.occurrence_id = ANY(%s) AND c.terminal
GROUP BY d.occurrence_id
"""


def track_stats_for_occurrences(occurrence_ids: list[int]) -> dict[int, dict]:
    """Stats keyed by occurrence id, in two statements scoped to the ids given.

    Occurrences with no detections are absent from the result. The cost is proportional
    to the detections behind the ids, not to the project, so keep a call to a page or a
    refresh batch of ids.
    """
    from ami.main.models import Classification, Detection, Occurrence, SourceImage

    if not occurrence_ids:
        return {}

    geometry_sql = _GEOMETRY_SQL.format(
        detection=Detection._meta.db_table,
        source_image=SourceImage._meta.db_table,
        min_area=_MIN_AREA,
    )
    classification_sql = _CLASSIFICATION_SQL.format(
        classification=Classification._meta.db_table,
        detection=Detection._meta.db_table,
        occurrence=Occurrence._meta.db_table,
    )

    stats: dict[int, dict] = {}
    with connection.cursor() as cursor:
        cursor.execute(geometry_sql, [list(occurrence_ids)])
        for pk, frames, path_length, min_area, max_area, max_width, max_height, max_x2, max_y2 in cursor.fetchall():
            diagonal = frame_diagonal(max_width, max_height, max_x2, max_y2)
            stats[pk] = {
                "frames": frames,
                "motion": round(float(path_length) / diagonal, _ROUND_TO),
                "size_ratio": size_ratio(min_area, max_area),
                "distinct_taxa": 0,
                "id_agreement": None,
            }

        cursor.execute(classification_sql, [list(occurrence_ids)])
        for pk, distinct, terminal_count, agreeing in cursor.fetchall():
            if pk in stats:
                stats[pk]["distinct_taxa"] = distinct
                stats[pk]["id_agreement"] = id_agreement(agreeing, terminal_count)

    return stats


def stored_track_stats(occurrence: Occurrence, frames: int) -> dict | None:
    """The list payload, read from the stored fields; None until they have been computed.

    ``track_motion`` is never null once stored (a single frame scores 0.0), so it stands
    in for all four. ``frames`` comes from the caller's ``detections_count`` annotation.
    """
    if occurrence.track_motion is None:
        return None
    return {
        "frames": frames,
        "motion": occurrence.track_motion,
        "size_ratio": occurrence.track_size_ratio,
        "distinct_taxa": occurrence.track_distinct_taxa,
        "id_agreement": occurrence.track_id_agreement,
    }


def _apply_stats(occurrence: Occurrence, stats: dict | None) -> None:
    occurrence.track_motion = stats["motion"] if stats else None
    occurrence.track_size_ratio = stats["size_ratio"] if stats else None
    occurrence.track_distinct_taxa = stats["distinct_taxa"] if stats else None
    occurrence.track_id_agreement = stats["id_agreement"] if stats else None


def refresh_track_stats(*occurrences: Occurrence) -> None:
    """Recompute the stored stats for these occurrences from their current detections.

    Three queries however many occurrences are given: the two statements of
    ``track_stats_for_occurrences`` and one ``bulk_update``. The instances are updated in
    place as well as the rows. An occurrence with no detections is set back to null.
    Call after the determination is settled, since ``id_agreement`` is measured against
    it, and without going through ``Occurrence.save()``, which would recompute it.
    """
    from ami.main.models import Occurrence

    targets = [occurrence for occurrence in occurrences if occurrence.pk is not None]
    if not targets:
        return
    stats = track_stats_for_occurrences([occurrence.pk for occurrence in targets])
    for occurrence in targets:
        _apply_stats(occurrence, stats.get(occurrence.pk))
    Occurrence.objects.bulk_update(targets, TRACK_STAT_FIELDS)


def refresh_track_stats_for_ids(occurrence_ids: Iterable[int]) -> int:
    """Refresh stored stats by id, in batches of ``REFRESH_BATCH_SIZE``; returns the count.

    Writes through ``bulk_update`` so ``updated_at`` is left alone: the list sorts by it
    by default, and a backfill must not reorder every occurrence in a project.
    """
    from ami.main.models import Occurrence

    ids = list(occurrence_ids)
    for start in range(0, len(ids), REFRESH_BATCH_SIZE):
        refresh_track_stats(*(Occurrence(pk=pk) for pk in ids[start : start + REFRESH_BATCH_SIZE]))
    return len(ids)


def tracking_algorithm_summary() -> dict | None:
    """The Algorithm row the tracking task registers itself under, or None if it never ran here."""
    from ami.ml.models.algorithm import Algorithm
    from ami.ml.post_processing.tracking_task import TrackingTask

    return Algorithm.objects.filter(key=TrackingTask.key).values("id", "name", "key").first()


def grouping_summary_from_prefetch(occurrence: Occurrence, algorithm: dict | None) -> dict:
    """Read-time description of how this occurrence's detections hang together.

    ``derived`` is a fixed marker: these numbers are computed from the current
    detections on every read, never stored and never exported. Requires
    ``OccurrenceQuerySet.with_detail_prefetches()``: the detections with their
    classifications and source_image, plus the ``frames_with_vectors`` annotation.
    """
    from ami.main.models_future.occurrence import _require_prefetch

    _require_prefetch(occurrence, "detections")
    frames_with_vectors = getattr(occurrence, "frames_with_vectors", None)
    if frames_with_vectors is None:
        raise RuntimeError(
            f"Occurrence {occurrence.pk} is missing the frames_with_vectors annotation. "
            "Apply OccurrenceQuerySet.with_detail_prefetches() in the viewset's get_queryset()."
        )
    detections = list(occurrence.detections.all())
    stats = track_stats_from_detections(detections, occurrence.determination_id)

    timestamps = [d.timestamp for d in detections if d.timestamp is not None]
    duration = (max(timestamps) - min(timestamps)).total_seconds() if timestamps else None

    scores = [c.score for d in detections for c in d.classifications.all() if c.terminal and c.score is not None]

    return {
        "derived": True,
        "algorithm": algorithm,
        "frames": stats["frames"],
        "frames_with_vectors": frames_with_vectors,
        "linked_detections": sum(1 for d in detections if d.next_detection_id is not None),
        "duration_seconds": duration,
        "motion": stats["motion"],
        "size_ratio": stats["size_ratio"],
        "distinct_taxa": stats["distinct_taxa"],
        "id_agreement": stats["id_agreement"],
        "score_min": round(min(scores), _ROUND_TO) if scores else None,
        "score_mean": round(statistics.fmean(scores), _ROUND_TO) if scores else None,
        "score_max": round(max(scores), _ROUND_TO) if scores else None,
    }
