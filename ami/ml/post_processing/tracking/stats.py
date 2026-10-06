"""Figures that describe one occurrence's path, computed from its detections' boxes and labels.

Nothing here touches Django or the database. Boxes are ``(x1, y1, x2, y2)`` in capture order, and
labels are the taxon ids of the occurrence's terminal classifications.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

BBox = Sequence[float]

_MIN_AREA = 1.0
_ROUND_TO = 4


@dataclass(frozen=True)
class OccurrenceFigures:
    detection_count: int
    motion: float
    size_ratio: float
    distinct_taxa: int
    id_agreement: float | None


def frame_diagonal(sizes: Sequence[tuple[int | None, int | None]], boxes: Sequence[BBox]) -> float:
    """The length motion is divided by, in the pixel units of the boxes.

    It is the diagonal of the largest capture width and height seen. Captures without dimensions fall back
    to the farthest box corner, and to 1.0 when there is no box either.
    """
    widths = [width for width, _ in sizes if width]
    heights = [height for _, height in sizes if height]
    if widths and heights:
        return math.hypot(max(widths), max(heights))
    far_x = max((box[2] for box in boxes), default=0.0)
    far_y = max((box[3] for box in boxes), default=0.0)
    return math.hypot(far_x, far_y) or 1.0


def motion(boxes: Sequence[BBox], diagonal: float) -> float:
    """Path length between consecutive box centres, as a fraction of ``diagonal``."""
    centres = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in boxes]
    path = sum(math.dist(a, b) for a, b in zip(centres, centres[1:]))
    return round(path / diagonal, _ROUND_TO)


def size_ratio(boxes: Sequence[BBox]) -> float:
    """Largest box area over the smallest, with areas floored at 1 so a degenerate box cannot divide by zero."""
    areas = [max(abs((box[2] - box[0]) * (box[3] - box[1])), _MIN_AREA) for box in boxes]
    if not areas:
        return 1.0
    return round(max(areas) / min(areas), _ROUND_TO)


def distinct_taxa(labels: Sequence[int | None]) -> int:
    """How many different taxa the labels name; a label without a taxon counts for none."""
    return len({label for label in labels if label is not None})


def id_agreement(labels: Sequence[int | None], determination_id: int | None) -> float | None:
    """The share of labels naming the determination, or None when there are no labels."""
    if not labels:
        return None
    return round(sum(label == determination_id and label is not None for label in labels) / len(labels), _ROUND_TO)


def occurrence_figures(
    boxes: Sequence[BBox],
    sizes: Sequence[tuple[int | None, int | None]],
    labels: Sequence[int | None],
    determination_id: int | None,
) -> OccurrenceFigures:
    """All the figures for one occurrence: ``sizes`` holds the width and height of each detection's capture."""
    return OccurrenceFigures(
        detection_count=len(boxes),
        motion=motion(boxes, frame_diagonal(sizes, boxes)),
        size_ratio=size_ratio(boxes),
        distinct_taxa=distinct_taxa(labels),
        id_agreement=id_agreement(labels, determination_id),
    )
