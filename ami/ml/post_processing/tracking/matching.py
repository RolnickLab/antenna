"""Pure matching rules that decide which detections in neighbouring captures are the same insect.

Nothing here touches Django or the database. Detections are passed as ``(id, bbox)`` pairs and
links come back as ``(id, next_id, cost)`` tuples, so the rules can be tested without models.
"""

import datetime
import math
from collections.abc import Sequence

from .config import TrackingConfig

BBox = Sequence[float]
Link = tuple[int, int, float]


def iou(bb1, bb2) -> float:
    xA = max(bb1[0], bb2[0])
    yA = max(bb1[1], bb2[1])
    xB = min(bb1[2], bb2[2])
    yB = min(bb1[3], bb2[3])
    inter = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    area1 = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    area2 = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def box_ratio(bb1, bb2) -> float:
    area1 = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    area2 = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)
    return min(area1, area2) / max(area1, area2)


def distance_ratio(bb1, bb2, img_diag: float) -> float:
    cx1 = (bb1[0] + bb1[2]) / 2
    cy1 = (bb1[1] + bb1[3]) / 2
    cx2 = (bb2[0] + bb2[2]) / 2
    cy2 = (bb2[1] + bb2[3]) / 2
    dist = math.sqrt((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2)
    return dist / img_diag if img_diag > 0 else 1.0


def image_diagonal(width: int, height: int) -> int:
    return int(math.ceil(math.sqrt(width**2 + height**2)))


def pair_cost(bb1, bb2, diag: float, config: TrackingConfig) -> float | None:
    """Matching cost between two detections; lower means more likely the same insect.

    Returns None when the pair fails an enabled limit, so it is never a candidate however
    low its cost. With default weights the cost is the plain sum of the three terms.
    """
    overlap = iou(bb1, bb2)
    size_ratio = box_ratio(bb1, bb2)
    distance = distance_ratio(bb1, bb2, diag)
    if config.min_iou is not None and overlap < config.min_iou:
        return None
    if config.min_size_ratio is not None and size_ratio < config.min_size_ratio:
        return None
    if config.max_distance is not None and distance > config.max_distance:
        return None
    return (
        config.iou_weight * (1 - overlap) + config.size_weight * (1 - size_ratio) + config.distance_weight * distance
    )


def captures_too_far_apart(
    first: datetime.datetime | None, second: datetime.datetime | None, config: TrackingConfig
) -> bool:
    """Is the gap between two capture times over the interval limit? A missing timestamp counts as too far."""
    if config.max_capture_interval_seconds is None:
        return False
    if first is None or second is None:
        return True
    return abs((second - first).total_seconds()) > config.max_capture_interval_seconds


def select_links(
    current_detections: Sequence[tuple[int, BBox]],
    next_detections: Sequence[tuple[int, BBox]],
    diag: float,
    config: TrackingConfig,
) -> list[Link]:
    """The links to make between two adjacent captures, lowest cost first.

    Each detection is an ``(id, bbox)`` pair. A pair is a candidate when it passes every enabled limit
    and its cost is below the cutoff. Candidates are taken lowest cost first, and each detection is
    linked at most once on either side.
    """
    candidates: list[Link] = []
    for det_id, det_box in current_detections:
        for next_id, next_box in next_detections:
            cost = pair_cost(det_box, next_box, diag, config)
            if cost is not None and cost < config.cost_threshold:
                candidates.append((det_id, next_id, cost))

    # Secondary keys keep tied costs deterministic across runs.
    candidates.sort(key=lambda x: (x[2], x[0], x[1]))

    claimed_current: set[int] = set()
    claimed_next: set[int] = set()
    links: list[Link] = []
    for det_id, next_id, cost in candidates:
        if det_id in claimed_current or next_id in claimed_next:
            continue
        claimed_current.add(det_id)
        claimed_next.add(next_id)
        links.append((det_id, next_id, cost))
    return links
