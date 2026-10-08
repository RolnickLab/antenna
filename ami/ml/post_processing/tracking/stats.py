"""Figures that describe one occurrence's path, computed from its detections' boxes and labels.

Nothing here touches Django or the database. Boxes are ``(x1, y1, x2, y2)`` in capture order, and
labels are the occurrence's terminal classifications.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

BBox = Sequence[float]

_MIN_AREA = 1.0
_ROUND_TO = 4


@dataclass(frozen=True)
class Label:
    """One terminal classification of a detection: the taxon it names, that taxon's name, and its score."""

    detection_id: int
    taxon_id: int | None
    taxon_name: str | None
    score: float | None


@dataclass(frozen=True)
class TaxonLabels:
    """How the labels of an occurrence's detections name one taxon.

    The name is copied when the figures are computed, so it still reads correctly after the taxon is
    renamed, merged into a synonym or deleted.
    """

    taxon_id: int
    name: str
    detection_count: int
    score_max: float | None


@dataclass(frozen=True)
class OccurrenceFigures:
    detection_count: int
    motion: float
    path_length: float
    size_change: float
    distinct_taxa: int
    label_agreement: float | None
    taxa: list[TaxonLabels]


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


def _raw_path_length(boxes: Sequence[BBox]) -> float:
    centres = [((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) for box in boxes]
    return sum(math.dist(a, b) for a, b in zip(centres, centres[1:]))


def path_length(boxes: Sequence[BBox], diagonal: float) -> float:
    """Total distance between consecutive box centres, as a fraction of ``diagonal``."""
    return round(_raw_path_length(boxes) / diagonal, _ROUND_TO)


def motion(boxes: Sequence[BBox], diagonal: float) -> float:
    """Mean distance per step between consecutive box centres, as a fraction of ``diagonal``; 0 for one box."""
    steps = len(boxes) - 1
    if steps < 1:
        return 0.0
    return round(_raw_path_length(boxes) / steps / diagonal, _ROUND_TO)


def size_change(boxes: Sequence[BBox]) -> float:
    """Largest box area over the smallest (at least 1); areas are floored at 1 so a degenerate box cannot divide by 0.

    The config's ``min_size_ratio`` is the opposite way round (smaller over larger, at most 1).
    """
    areas = [max(abs((box[2] - box[0]) * (box[3] - box[1])), _MIN_AREA) for box in boxes]
    if not areas:
        return 1.0
    return round(max(areas) / min(areas), _ROUND_TO)


def distinct_taxa(labels: Sequence[int | None]) -> int:
    """How many different taxa the labels name; a label without a taxon counts for none."""
    return len({label for label in labels if label is not None})


def label_agreement(labels: Sequence[int | None], determination_id: int | None) -> float | None:
    """The share of labels naming the determination, or None when there are no labels.

    Labels are machine classifications, not human identifications.
    """
    if not labels:
        return None
    return round(sum(label == determination_id and label is not None for label in labels) / len(labels), _ROUND_TO)


def taxa_named(labels: Sequence[Label]) -> list[TaxonLabels]:
    """Each taxon the labels name, with how many detections it labels and its best score.

    Most detections first, then the best score; a label without a taxon is left out. A low best score
    shows a taxon that was never more than a minor guess.
    """
    detections: dict[int, set[int]] = {}
    best: dict[int, float | None] = {}
    names: dict[int, str] = {}
    for label in labels:
        if label.taxon_id is None:
            continue
        detections.setdefault(label.taxon_id, set()).add(label.detection_id)
        names.setdefault(label.taxon_id, label.taxon_name or "")
        if label.score is not None:
            current = best.get(label.taxon_id)
            best[label.taxon_id] = label.score if current is None else max(current, label.score)
    taxa = [
        TaxonLabels(
            taxon_id=taxon_id,
            name=names[taxon_id],
            detection_count=len(detection_ids),
            score_max=round(best[taxon_id], _ROUND_TO) if best.get(taxon_id) is not None else None,
        )
        for taxon_id, detection_ids in detections.items()
    ]
    return sorted(taxa, key=lambda t: (-t.detection_count, -(t.score_max or 0.0), t.taxon_id))


def occurrence_figures(
    boxes: Sequence[BBox],
    sizes: Sequence[tuple[int | None, int | None]],
    labels: Sequence[Label],
    determination_id: int | None,
) -> OccurrenceFigures:
    """All the figures for one occurrence: ``sizes`` holds the width and height of each detection's capture."""
    diagonal = frame_diagonal(sizes, boxes)
    taxon_ids = [label.taxon_id for label in labels]
    return OccurrenceFigures(
        detection_count=len(boxes),
        motion=motion(boxes, diagonal),
        path_length=path_length(boxes, diagonal),
        size_change=size_change(boxes),
        distinct_taxa=distinct_taxa(taxon_ids),
        label_agreement=label_agreement(taxon_ids, determination_id),
        taxa=taxa_named(labels),
    )
