"""
Stored occurrence sizes, used to filter and sort occurrences by how big the insect appears.

An occurrence's size is the median, over its detections, of the bounding box's longest side:

- ``relative_length``: as a fraction of the capture's longest side. Comparable across image
  resolutions and across portrait and landscape captures, so it works for every project.
- ``length_mm``: in millimetres, when the capture's station has a calibrated field of view
  (``Deployment.frame_long_side_mm`` and ``frame_short_side_mm``). A capture whose aspect ratio
  does not match the calibrated frame (for example a cropped camera mode) is left out.

The values are stored on the occurrence instead of computed per request because filtering on a
per-request aggregate over detections made occurrence counts about 20x slower on large projects.
Every code path that attaches detections to occurrences or changes a station's calibration must
call ``update_occurrence_sizes``. See #377.

This module uses raw SQL and imports no models, so ``ami.main.models`` can call it.
"""

from __future__ import annotations

import logging
import typing

from django.db import connection
from django.db.models import QuerySet

logger = logging.getLogger(__name__)

# A capture counts as calibrated only when its pixel aspect ratio is within this fraction of the
# calibrated frame's aspect ratio (long side / short side in mm).
CALIBRATION_ASPECT_TOLERANCE = 0.05

UPDATE_BATCH_SIZE = 5000

# One row per detection with a usable box and known capture dimensions. A box must have four
# numeric coordinates, a positive width and height, and fit inside the capture (1 px tolerance);
# anything else is treated as unknown rather than guessed.
_UPDATE_SQL = """
WITH boxes AS (
    SELECT
        d.occurrence_id,
        si.width AS image_w,
        si.height AS image_h,
        dep.frame_long_side_mm AS long_mm,
        dep.frame_short_side_mm AS short_mm,
        CASE WHEN jsonb_typeof(d.bbox) = 'array'
                  AND jsonb_array_length(d.bbox) = 4
                  AND jsonb_typeof(d.bbox -> 0) = 'number'
                  AND jsonb_typeof(d.bbox -> 1) = 'number'
                  AND jsonb_typeof(d.bbox -> 2) = 'number'
                  AND jsonb_typeof(d.bbox -> 3) = 'number'
             THEN ARRAY[(d.bbox ->> 0)::float, (d.bbox ->> 1)::float,
                        (d.bbox ->> 2)::float, (d.bbox ->> 3)::float]
        END AS b
    FROM main_detection d
    JOIN main_sourceimage si ON si.id = d.source_image_id
    LEFT JOIN main_deployment dep ON dep.id = si.deployment_id
    WHERE d.occurrence_id = ANY(%(ids)s)
      AND si.width > 0 AND si.height > 0
),
lengths AS (
    SELECT
        occurrence_id,
        GREATEST(b[3] - b[1], b[4] - b[2]) / GREATEST(image_w, image_h)::float AS rel_len,
        CASE WHEN long_mm > 0 AND short_mm > 0
                  AND abs((long_mm / short_mm)
                          / (GREATEST(image_w, image_h)::float / LEAST(image_w, image_h)) - 1)
                      <= %(aspect_tolerance)s
             THEN GREATEST(b[3] - b[1], b[4] - b[2]) * long_mm / GREATEST(image_w, image_h)
        END AS len_mm
    FROM boxes
    WHERE b IS NOT NULL
      AND b[3] > b[1] AND b[4] > b[2]
      AND b[1] >= -1 AND b[2] >= -1
      AND b[3] <= image_w + 1 AND b[4] <= image_h + 1
),
sizes AS (
    SELECT
        t.id,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY l.rel_len) AS relative_length,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY l.len_mm) AS length_mm
    FROM unnest(%(ids)s::bigint[]) AS t(id)
    LEFT JOIN lengths l ON l.occurrence_id = t.id
    GROUP BY t.id
)
UPDATE main_occurrence o
SET relative_length = s.relative_length, length_mm = s.length_mm
FROM sizes s
WHERE o.id = s.id
  AND (o.relative_length IS DISTINCT FROM s.relative_length OR o.length_mm IS DISTINCT FROM s.length_mm)
"""


def update_occurrence_sizes(occurrence_ids: typing.Iterable[int]) -> int:
    """
    Recalculate the stored size of the given occurrences from their detections.

    Occurrences with no usable detection box get ``None``. Rows whose size did not change are not
    written. Returns the number of occurrences updated.
    """
    ids = sorted({int(pk) for pk in occurrence_ids if pk is not None})
    updated = 0
    for start in range(0, len(ids), UPDATE_BATCH_SIZE):
        batch = ids[start : start + UPDATE_BATCH_SIZE]
        with connection.cursor() as cursor:
            cursor.execute(_UPDATE_SQL, {"ids": batch, "aspect_tolerance": CALIBRATION_ASPECT_TOLERANCE})
            updated += cursor.rowcount
    return updated


def update_occurrence_sizes_in_queryset(occurrences: QuerySet, batch_size: int = UPDATE_BATCH_SIZE) -> int:
    """Recalculate the stored size of every occurrence in ``occurrences``, one batch of ids at a time."""
    updated = 0
    batch: list[int] = []
    for pk in occurrences.order_by("pk").values_list("pk", flat=True).iterator(chunk_size=batch_size):
        batch.append(pk)
        if len(batch) >= batch_size:
            updated += update_occurrence_sizes(batch)
            batch = []
    if batch:
        updated += update_occurrence_sizes(batch)
    return updated
