import dataclasses
import logging
import math
import typing
from collections.abc import Iterable

import numpy as np
from django.db.models import Count

from ami.main.models import Classification, Detection, Event, Occurrence, SourceImage
from ami.ml.models import Algorithm
from ami.ml.post_processing.base import BasePostProcessingTask

if typing.TYPE_CHECKING:
    pass


@dataclasses.dataclass
class TrackingParams:
    cost_threshold: float = 0.2
    skip_if_human_identifications: bool = True
    require_completely_processed_session: bool = False
    feature_extraction_algorithm_id: int | None = None


DEFAULT_TRACKING_PARAMS = TrackingParams()


def cosine_similarity(v1: Iterable[float], v2: Iterable[float]) -> float:
    a = np.array(v1)
    b = np.array(v2)
    sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.clip(sim, 0.0, 1.0))


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


def total_cost(f1, f2, bb1, bb2, diag) -> float:
    return (
        (1 - cosine_similarity(f1, f2))
        + (1 - iou(bb1, bb2))
        + (1 - box_ratio(bb1, bb2))
        + distance_ratio(bb1, bb2, diag)
    )


def get_most_common_algorithm_for_event(event: Event) -> Algorithm | None:
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


def event_fully_processed(event: Event, logger: logging.Logger, algorithm: Algorithm) -> bool:
    total = event.captures.count()
    processed = (
        event.captures.filter(
            detections__classifications__features_2048__isnull=False,
            detections__classifications__algorithm=algorithm,
        )
        .distinct()
        .count()
    )
    if processed < total:
        logger.info(f"Event {event.pk} not fully processed: {processed}/{total} captures")
        return False
    return True


def get_feature_vector(detection: Detection, algorithm: Algorithm):
    return (
        detection.classifications.filter(features_2048__isnull=False, algorithm=algorithm)
        .order_by("-timestamp")
        .values_list("features_2048", flat=True)
        .first()
    )


def assign_occurrences_from_detection_chains(source_images: list[SourceImage], logger: logging.Logger) -> None:
    visited: set[int] = set()
    created = 0
    existing = Occurrence.objects.filter(detections__source_image__in=source_images).distinct().count()

    for image in source_images:
        for det in image.detections.all():
            if det.pk in visited or getattr(det, "previous_detection", None) is not None:
                continue

            chain: list[Detection] = []
            current: Detection | None = det
            while current and current.pk not in visited:
                chain.append(current)
                visited.add(current.pk)
                current = current.next_detection

            if len(chain) <= 1:
                continue

            old_occ_ids = {d.occurrence_id for d in chain if d.occurrence_id}
            if len(old_occ_ids) == 1:
                # All detections already share one occurrence; nothing to do.
                continue

            for occ_id in old_occ_ids:
                # @TODO consider soft-delete or detach instead of hard-delete.
                try:
                    Occurrence.objects.filter(id=occ_id).delete()
                except Exception as e:
                    logger.error(f"Failed to delete occurrence {occ_id}: {e}")

            occurrence = Occurrence.objects.create(
                event=chain[0].source_image.event,
                deployment=chain[0].source_image.deployment,
                project=chain[0].source_image.project,
            )
            created += 1

            for d in chain:
                d.occurrence = occurrence
                d.save()

            occurrence.save()

    new_count = Occurrence.objects.filter(detections__source_image__in=source_images).distinct().count()
    removed = existing - new_count
    if removed > 0:
        logger.info(f"Reduced existing occurrences by {removed}.")
    logger.info(
        f"Assigned {created} new occurrences across {len(source_images)} images. "
        f"Occurrences before: {existing}, after: {new_count}. Detections processed: {len(visited)}."
    )


def pair_detections(
    current_detections: list[Detection],
    next_detections: list[Detection],
    image_width: int,
    image_height: int,
    cost_threshold: float,
    algorithm: Algorithm,
    logger: logging.Logger,
) -> None:
    """
    Greedy lowest-cost matching between two adjacent images. Sets `next_detection`
    on each detection in `current_detections` for the best partner in `next_detections`,
    if that partner's cost is below `cost_threshold` and not already claimed.
    """
    diag = image_diagonal(image_width, image_height)
    candidates: list[tuple[Detection, Detection, float]] = []

    for det in current_detections:
        det_vec = get_feature_vector(det, algorithm)
        if det_vec is None:
            continue
        for nxt in next_detections:
            nxt_vec = get_feature_vector(nxt, algorithm)
            if nxt_vec is None:
                continue
            cost = total_cost(det_vec, nxt_vec, det.bbox, nxt.bbox, diag)
            if cost < cost_threshold:
                candidates.append((det, nxt, cost))

    candidates.sort(key=lambda x: x[2])

    claimed_current: set[int] = set()
    claimed_next: set[int] = set()

    for det, nxt, cost in candidates:
        if det.id in claimed_current or nxt.id in claimed_next:
            continue
        # Detach any existing inbound link to `nxt` before reassigning.
        prior: Detection | None = getattr(nxt, "previous_detection", None)
        if prior is not None:
            prior.next_detection = None
            prior.save()

        det.next_detection = nxt
        det.save()
        claimed_current.add(det.id)
        claimed_next.add(nxt.id)
        logger.debug(f"Linked detection {det.id} -> {nxt.id} (cost {cost:.4f})")


def assign_occurrences_by_tracking_images(
    event: Event,
    logger: logging.Logger,
    algorithm: Algorithm,
    params: TrackingParams = DEFAULT_TRACKING_PARAMS,
    progress_cb: typing.Callable[[float], None] | None = None,
) -> None:
    source_images = list(event.captures.order_by("timestamp"))
    if len(source_images) < 2:
        logger.warning(f"Event {event.pk}: not enough images to track ({len(source_images)})")
        return

    transitions = len(source_images) - 1
    for i in range(transitions):
        cur = source_images[i]
        nxt = source_images[i + 1]

        if not cur.width or not cur.height:
            logger.warning(f"Image {cur.pk} has no dimensions; aborting tracking for event {event.pk}")
            return

        pair_detections(
            list(cur.detections.all()),
            list(nxt.detections.all()),
            image_width=cur.width,
            image_height=cur.height,
            cost_threshold=params.cost_threshold,
            algorithm=algorithm,
            logger=logger,
        )
        if progress_cb:
            progress_cb((i + 1) / transitions)

    assign_occurrences_from_detection_chains(source_images, logger)


class TrackingTask(BasePostProcessingTask):
    """
    Reconstruct occurrences in a SourceImageCollection by tracking detections across
    consecutive captures using feature embeddings + bbox geometry. Updates each
    Detection's `next_detection` link and creates one Occurrence per chain.
    """

    key = "tracking"
    name = "Occurrence Tracking"

    def _params(self) -> TrackingParams:
        config_keys = {f.name for f in dataclasses.fields(TrackingParams)}
        overrides = {k: v for k, v in self.config.items() if k in config_keys}
        unknown = set(self.config) - config_keys - {"source_image_collection_id"}
        if unknown:
            self.logger.warning(f"Ignoring unknown tracking config keys: {sorted(unknown)}")
        return dataclasses.replace(DEFAULT_TRACKING_PARAMS, **overrides)

    def _resolve_collection(self):
        from ami.main.models import SourceImageCollection

        if self.job and self.job.source_image_collection:
            return self.job.source_image_collection

        collection_id = self.config.get("source_image_collection_id")
        if not collection_id:
            raise ValueError(
                "Tracking task requires a source image collection. "
                "Set it on the job or pass `source_image_collection_id` in config."
            )
        return SourceImageCollection.objects.get(pk=collection_id)

    def run(self) -> None:
        params = self._params()
        self.logger.info(f"Tracking starting with params: {params}")

        collection = self._resolve_collection()
        events_qs = Event.objects.filter(captures__collections=collection).order_by("created_at").distinct()
        events = list(events_qs)
        total = len(events)
        self.logger.info(f"Tracking: {total} events in collection {collection.pk}")

        for idx, event in enumerate(events, start=1):
            self.logger.info(f"Tracking event {idx}/{total} (id={event.pk})")

            algorithm = get_most_common_algorithm_for_event(event)
            if algorithm is None:
                self.logger.warning(f"No feature-extraction algorithm found for event {event.pk}; skipping.")
                continue

            if (
                params.skip_if_human_identifications
                and Occurrence.objects.filter(event=event, identifications__isnull=False).exists()
            ):
                self.logger.info(f"Skipping event {event.pk}: has human identifications.")
                continue

            if params.require_completely_processed_session and not event_fully_processed(
                event, logger=self.logger, algorithm=algorithm
            ):
                self.logger.info(f"Skipping event {event.pk}: not fully processed.")
                continue

            def _stage_progress(p: float, _idx=idx, _total=total) -> None:
                # Aggregate per-event progress into overall task progress.
                overall = ((_idx - 1) + p) / _total
                self.update_progress(overall)

            assign_occurrences_by_tracking_images(
                event=event,
                logger=self.logger,
                algorithm=algorithm,
                params=params,
                progress_cb=_stage_progress,
            )

        self.update_progress(1.0)
        self.logger.info("Tracking finished.")
