import math
from collections import defaultdict
from collections.abc import Iterable

import numpy as np

from ami.main.models import Detection, Occurrence

TRACKING_COST_THRESHOLD = 2


def cosine_similarity(v1: Iterable[float], v2: Iterable[float]) -> float:
    v1 = np.array(v1)
    v2 = np.array(v2)
    sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return float(np.clip(sim, 0.0, 1.0))


def iou(bb1, bb2):
    xA = max(bb1[0], bb2[0])
    yA = max(bb1[1], bb2[1])
    xB = min(bb1[2], bb2[2])
    yB = min(bb1[3], bb2[3])
    interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    boxAArea = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    boxBArea = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)
    unionArea = boxAArea + boxBArea - interArea
    return interArea / unionArea if unionArea > 0 else 0


def box_ratio(bb1, bb2):
    area1 = (bb1[2] - bb1[0] + 1) * (bb1[3] - bb1[1] + 1)
    area2 = (bb2[2] - bb2[0] + 1) * (bb2[3] - bb2[1] + 1)
    return min(area1, area2) / max(area1, area2)


def distance_ratio(bb1, bb2, img_diag):
    cx1 = (bb1[0] + bb1[2]) / 2
    cy1 = (bb1[1] + bb1[3]) / 2
    cx2 = (bb2[0] + bb2[2]) / 2
    cy2 = (bb2[1] + bb2[3]) / 2
    dist = math.sqrt((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2)
    return dist / img_diag if img_diag > 0 else 1.0


def image_diagonal(width: int, height: int) -> int:
    img_diagonal = int(math.ceil(math.sqrt(width**2 + height**2)))
    return img_diagonal


def total_cost(f1, f2, bb1, bb2, diag):
    return (
        (1 - cosine_similarity(f1, f2))
        + (1 - iou(bb1, bb2))
        + (1 - box_ratio(bb1, bb2))
        + distance_ratio(bb1, bb2, diag)
    )


def get_latest_feature_vector(detection: Detection):
    return (
        detection.classifications.filter(features_2048__isnull=False)
        .order_by("-timestamp")
        .values_list("features_2048", flat=True)
        .first()
    )


def assign_occurrences_by_tracking(
    detections: list[Detection],
    logger,
) -> None:
    """
    Perform object tracking by assigning detections across multiple source images
    to the same Occurrence if they are similar enough, based on the latest classification feature vectors.
    """
    logger.info(f"Starting to assign occurrences by tracking. {len(detections)} detections found.")

    # Group detections by source image timestamp
    image_to_dets = defaultdict(list)
    for det in detections:
        image_to_dets[det.source_image.timestamp].append(det)
    sorted_timestamps = sorted(image_to_dets.keys())
    logger.info(f"Found {len(sorted_timestamps)} source images with detections.")

    last_detections = []

    for timestamp in sorted_timestamps:
        current_detections = image_to_dets[timestamp]
        logger.info(f"Processing {len(current_detections)} detections at {timestamp}")

        for det in current_detections:
            det_vec = get_latest_feature_vector(det)
            if det_vec is None:
                logger.info(f"No features for detection {det.id}, skipping.")
                continue

            best_match = None
            best_cost = float("inf")

            for prev in last_detections:
                prev_vec = get_latest_feature_vector(prev)
                if prev_vec is None:
                    continue

                cost = total_cost(
                    det_vec,
                    prev_vec,
                    det.bbox,
                    prev.bbox,
                    image_diagonal(det.source_image.width, det.source_image.height),
                )

                logger.info(f"Comparing detection {det.id} with previous {prev.id}: cost = {cost:.4f}")
                if cost < best_cost:
                    best_cost = cost
                    best_match = prev

            if best_match and best_cost < TRACKING_COST_THRESHOLD:
                det.occurrence = best_match.occurrence
                logger.info(f"Assigned detection {det.id} to existing occurrence {best_match.occurrence.pk}")
            else:
                occurrence = Occurrence.objects.create(event=det.source_image.event)
                det.occurrence = occurrence
                logger.info(f"Created new occurrence {occurrence.pk} for detection {det.id}")

            det.save()

        last_detections = current_detections

    logger.info("Finished assigning occurrences by tracking.")
