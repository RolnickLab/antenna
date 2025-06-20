import math
from collections.abc import Iterable

import numpy as np
from django.db.models import Count

from ami.main.models import Classification, Detection, Event, Occurrence
from ami.ml.models import Algorithm

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


def get_most_common_algorithm_for_event(event):
    """
    Returns the most common Algorithm object (used in classifications with features_2048) for the given event.
    """
    most_common = (
        Classification.objects.filter(
            detection__source_image__event=event,
            features_2048__isnull=False,
        )
        .values("algorithm_id")
        .annotate(count=Count("id"))
        .order_by("-count")
        .first()
    )

    if most_common:
        return Algorithm.objects.get(id=most_common["algorithm_id"])

    return None


def event_fully_processed(event, logger) -> bool:
    """
    Checks if all captures in the event have processed detections with features_2048
    """
    total_captures = event.captures.count()
    logger.info(f"Checking if event {event.pk} is fully processed... Total captures: {total_captures}")

    processed_captures = (
        event.captures.filter(
            detections__classifications__features_2048__isnull=False,
        )
        .distinct()
        .count()
    )

    if processed_captures < total_captures:
        logger.info(
            f"Event {event.pk} is not fully processed. "
            f"Only {processed_captures}/{total_captures} captures have processed detections."
        )
        return False

    logger.info(f"Event {event.pk} is fully processed.")
    return True


def get_feature_vector(detection: Detection, algorithm: Algorithm):
    """
    Returns the latest non-null features_2048 vector from the given detection,
    extracted by a specific algorithm.
    """
    return (
        detection.classifications.filter(features_2048__isnull=False, algorithm=algorithm)
        .order_by("-timestamp")
        .values_list("features_2048", flat=True)
        .first()
    )


def assign_occurrences_from_detection_chains(source_images, logger):
    """
    Walk detection chains across source images and assign a new occurrence to each chain.
    """
    visited = set()
    created_occurrences_count = 0
    for image in source_images:
        for det in image.detections.all():
            if det.id in visited or getattr(det, "previous_detection", None) is not None:
                continue  # Already processed or this is not a chain start

            chain = []
            current = det
            while current and current.id not in visited:
                chain.append(current)
                visited.add(current.id)
                current = current.next_detection

            if chain:
                old_occurrences = {d.occurrence_id for d in chain if d.occurrence_id}

                # Delete old occurrences (if any)
                for occ_id in old_occurrences:
                    try:
                        Occurrence.objects.filter(id=occ_id).delete()
                        logger.debug(f"Deleted old occurrence {occ_id} before reassignment.")
                    except Exception as e:
                        logger.info(f"Failed to delete occurrence {occ_id}: {e}")

                occurrence = Occurrence.objects.create(
                    event=chain[0].source_image.event,
                    deployment=chain[0].source_image.deployment,
                    project=chain[0].source_image.project,
                )
                created_occurrences_count += 1

                for d in chain:
                    d.occurrence = occurrence
                    d.save()

                occurrence.save()

                logger.debug(f"Assigned occurrence {occurrence.pk} to chain of {len(chain)} detections")
    logger.info(
        f"Assigned {created_occurrences_count} occurrences from detection chains across {len(source_images)} images."
    )


def assign_occurrences_by_tracking_images(
    event, logger, cost_threshold: float = TRACKING_COST_THRESHOLD, job=None
) -> None:
    """
    Track detections across ordered source images and assign them to occurrences.
    """
    from ami.jobs.models import JobState

    source_images = event.captures.order_by("timestamp")
    logger.info(f"Found {len(source_images)} source images for event {event.pk}")
    if len(source_images) < 2:
        logger.info("Not enough images to perform tracking. At least 2 images are required.")
        return
    for i in range(len(source_images) - 1):
        current_image = source_images[i]
        next_image = source_images[i + 1]

        current_detections = list(current_image.detections.all())
        next_detections = list(next_image.detections.all())

        logger.debug(f"""Tracking: Processing image {i + 1}/{len(source_images)}""")
        # Get the most common algorithm for the current event
        most_common_algorithm = get_most_common_algorithm_for_event(current_image.event)
        logger.debug(
            f"""Using most common algorithm for event {current_image.event.pk}:
            {most_common_algorithm.name if most_common_algorithm else 'None'}"""
        )

        pair_detections(
            current_detections,
            next_detections,
            image_width=current_image.width,
            image_height=current_image.height,
            cost_threshold=cost_threshold,
            algorithm=most_common_algorithm,
            logger=logger,
        )
        if job:
            job.progress.update_stage(
                f"event_{event.pk}",
                status=JobState.STARTED,
                progress=(i + 1) / (len(source_images) - 1),
            )
            job.save()

    assign_occurrences_from_detection_chains(source_images, logger)
    if job:
        job.progress.update_stage(
            f"event_{event.pk}",
            progress=1.0,
        )
        job.save()


def pair_detections(
    current_detections: list,
    next_detections: list,
    image_width: int,
    image_height: int,
    cost_threshold: float,
    algorithm,
    logger,
) -> None:
    """
    Assigns next_detection for each detection in current_detections based on lowest cost match
    from next_detections, ensuring unique assignments and no duplicates.

    Only pairs with cost < threshold are considered.
    """
    logger.debug(f"Pairing {len(current_detections)} - >{len(next_detections)} detections")

    potential_matches = []

    for det in current_detections:
        det_vec = get_feature_vector(det, algorithm)
        if det_vec is None:
            logger.debug(f"Skipping detection {det.id} (no features)")
            continue

        for next_det in next_detections:
            next_vec = get_feature_vector(next_det, algorithm)
            if next_vec is None:
                logger.debug(f"Skipping next detection {next_det.id} (no features)")
                continue

            cost = total_cost(
                det_vec,
                next_vec,
                det.bbox,
                next_det.bbox,
                image_diagonal(image_width, image_height),
            )

            if cost < cost_threshold:
                potential_matches.append((det, next_det, cost))

    # Sort by cost: lower is better
    potential_matches.sort(key=lambda x: x[2])

    assigned_current_ids = set()
    assigned_next_ids = set()

    for det, next_det, cost in potential_matches:
        if det.id in assigned_current_ids or next_det.id in assigned_next_ids:
            continue
        # check if next detection has a previous detection already assigned
        if getattr(next_det, "previous_detection", None) is not None:
            logger.debug(f"{next_det.id} already has previous detection: {next_det.previous_detection.id}")
            previous_detection = getattr(next_det, "previous_detection", None)
            previous_detection.next_detection = None
            previous_detection.save()
            logger.debug(f"Cleared previous detection {previous_detection.pk} -> {next_det.pk}  link")

        logger.debug(f"Trying to link {det.id} => {next_det.id}")
        det.next_detection = next_det
        det.save()
        logger.debug(f"Linked detection {det.id} => {next_det.id} with cost {cost:.4f}")

        assigned_current_ids.add(det.id)
        assigned_next_ids.add(next_det.id)


def perform_tracking(job):
    """
    Perform detection tracking for all events in the job's source image collection.
    Runs tracking only if all images in an event have processed detections with features.
    """

    cost_threshold = job.params.get("cost_threshold", TRACKING_COST_THRESHOLD)
    job.logger.info("Tracking started")
    job.logger.info(f"Using cost threshold: {cost_threshold}")
    collection = job.source_image_collection
    if not collection:
        job.logger.info("Tracking: No source image collection found. Skipping tracking.")
        return
    job.logger.info("Tracking: Fetching events for collection %s", collection.pk)
    events_qs = Event.objects.filter(captures__collections=collection).order_by("created_at").distinct()
    total_events = events_qs.count()
    events = events_qs.iterator()
    job.logger.info("Tracking: Found %d events in collection %s", total_events, collection.pk)
    for event in events_qs:
        job.progress.add_stage(name=f"Event {event.pk}", key=f"event_{event.pk}")
        job.save()
    for idx, event in enumerate(events, start=1):
        job.logger.info(f"Tracking: Processing event {idx}/{total_events} (Event ID: {event.pk})")

        # Check if there are human identifications in the event
        if Occurrence.objects.filter(event=event, identifications__isnull=False).exists():
            job.logger.info(f"Tracking: Skipping tracking for event {event.pk}: human identifications present.")
            continue
        # Check if the all captures in the event have processed detections with features
        if not event_fully_processed(event, logger=job.logger):
            job.logger.info(
                f"Tracking: Skipping tracking for event {event.pk}: not all detections are fully processed."
            )
            continue

        job.logger.info(f"Tracking: Running tracking for event {event.pk}")
        assign_occurrences_by_tracking_images(event, job.logger, cost_threshold=cost_threshold, job=job)

    job.logger.info("Tracking: Finished tracking.")
    job.save()
