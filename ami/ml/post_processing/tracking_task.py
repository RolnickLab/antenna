import logging
import math
import typing
from collections.abc import Iterable

import numpy as np
import pydantic
from django.db import transaction
from django.db.models import Count

from ami.main.models import Classification, Detection, Event, Occurrence, SourceImage, SourceImageCollection
from ami.ml.models import Algorithm
from ami.ml.post_processing.base import BasePostProcessingTask


class TrackingConfig(pydantic.BaseModel):
    """Scope and tunables for a tracking run.

    Scope: exactly one of ``source_image_collection_id`` or ``event_ids`` says
    which sessions to track. A capture set is the bulk path; an explicit event
    list is what the Events admin page sends.
    """

    source_image_collection_id: int | None = None
    event_ids: list[int] = []

    # Maximum matching cost between two detections in consecutive captures. The cost
    # sums (1 - cosine similarity of embeddings), (1 - IoU), (1 - box area ratio) and
    # (centre distance / image diagonal), so a lower threshold links only detections
    # that barely moved and look alike.
    # WARNING: the default is calibrated against synthetic features in tests. Tune it
    # per dataset, and raise it when running without embeddings (see require_features).
    cost_threshold: float = 0.2

    # When True, a pair of detections is only considered if both carry a feature
    # embedding. When False, pairs without embeddings are still matched on geometry
    # alone (the appearance term is dropped, which makes matching more permissive) —
    # this is what lets tracking run on data processed before embeddings were stored.
    require_features: bool = True

    skip_if_human_identifications: bool = True
    require_completely_processed_session: bool = False

    # v1 only operates on fresh data: every detection has its own auto-created
    # occurrence (1:1) and no chain links exist yet. Re-tracking previously-tracked
    # data is a v2 concern (see #1272 for the incremental append/prepend plan).
    require_fresh_event: bool = True

    # Which feature extractor's embeddings to compare. Left unset, the task infers it
    # when exactly one algorithm produced embeddings for the event.
    feature_extraction_algorithm_id: int | None = None

    @pydantic.root_validator(skip_on_failure=True)
    def _exactly_one_scope(cls, values: dict) -> dict:
        scopes = [values.get("source_image_collection_id"), values.get("event_ids") or None]
        if sum(s is not None for s in scopes) != 1:
            raise ValueError("Provide exactly one of source_image_collection_id or event_ids")
        return values

    class Config:
        extra = "forbid"


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
    """Matching cost between two detections; lower means more likely the same insect.

    The appearance term is dropped when either detection has no embedding, leaving
    a geometry-only cost. Dropping a non-negative term lowers the total, so a
    geometry-only run matches more readily at the same threshold.
    """
    geometry = (1 - iou(bb1, bb2)) + (1 - box_ratio(bb1, bb2)) + distance_ratio(bb1, bb2, diag)
    if f1 is None or f2 is None:
        return geometry
    return (1 - cosine_similarity(f1, f2)) + geometry


def get_unique_feature_algorithm_for_event(event: Event) -> tuple[Algorithm | None, list[Algorithm]]:
    """
    Return ``(unique_algorithm, all_candidates)``.

    If exactly one feature-extraction algorithm produced ``features_2048`` for this
    event, returns that algorithm and a single-element list. Otherwise returns
    ``(None, candidates)`` so the caller can either skip with a warning or require
    the operator to pass an explicit ``feature_extraction_algorithm_id``.
    """
    algo_ids = (
        Classification.objects.filter(
            detection__source_image__event=event,
            features_2048__isnull=False,
            algorithm_id__isnull=False,
        )
        .values_list("algorithm_id", flat=True)
        .distinct()
    )
    candidates = list(Algorithm.objects.filter(pk__in=list(algo_ids)))
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def event_is_fresh(event: Event) -> tuple[bool, str]:
    """
    Fresh = every detection in the event has an occurrence AND every occurrence
    in the event has exactly one detection. v1 tracking only operates on fresh
    data (the state after pipeline processing creates 1:1 detection/occurrence
    auto-mappings, before any chain consolidation).
    """
    orphan_detections = Detection.objects.filter(
        source_image__event=event,
        occurrence__isnull=True,
    ).count()
    if orphan_detections:
        return False, f"{orphan_detections} detection(s) without an occurrence"

    multi_detection_occurrences = (
        Occurrence.objects.filter(event=event).annotate(_n=Count("detections")).filter(_n__gt=1).count()
    )
    if multi_detection_occurrences:
        return False, f"{multi_detection_occurrences} occurrence(s) already span >1 detection"

    return True, ""


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


def assign_occurrences_from_detection_chains(
    source_images: list[SourceImage], logger: logging.Logger
) -> dict[str, int]:
    """
    Walk chains via ``Detection.next_detection`` and consolidate each chain into
    a single occurrence using a merge-into-first strategy:

    - Pick the first existing occurrence in the chain as the keeper.
    - Reassign every other detection in the chain to the keeper.
    - Delete now-empty sibling occurrences.
    - If no detection in the chain has an occurrence yet, create one.

    Designed for fresh-event input (1:1 detection/occurrence). v2 incremental tracking
    can reuse this primitive for prepend/append: keeper survives, new detections fold in.

    Returns counters for the caller's stage metrics.
    """
    visited: set[int] = set()
    created = 0
    merged = 0
    existing = Occurrence.objects.filter(detections__source_image__in=source_images).distinct().count()

    for image in source_images:
        for det in image.detections.all():
            if det.pk in visited:
                continue
            try:
                has_prior = det.previous_detection is not None
            except Detection.DoesNotExist:
                has_prior = False
            if has_prior:
                continue

            chain: list[Detection] = []
            current: Detection | None = det
            while current and current.pk not in visited:
                chain.append(current)
                visited.add(current.pk)
                current = current.next_detection

            old_occ_ids = {d.occurrence_id for d in chain if d.occurrence_id}
            all_assigned = all(d.occurrence_id is not None for d in chain)

            # Coherent: every detection assigned and all share one occurrence. Nothing to do.
            if len(old_occ_ids) == 1 and all_assigned:
                continue

            # Pick keeper: first existing occurrence in chain order.
            keeper: Occurrence | None = None
            for d in chain:
                if d.occurrence_id:
                    keeper = d.occurrence
                    break

            if keeper is None:
                keeper = Occurrence.objects.create(
                    event=chain[0].source_image.event,
                    deployment=chain[0].source_image.deployment,
                    project=chain[0].source_image.project,
                )
                created += 1

            # Reassign chain detections to keeper.
            for d in chain:
                if d.occurrence_id != keeper.pk:
                    d.occurrence = keeper
                    d.save()

            # Delete now-empty sibling occurrences. v1's fresh-event invariant guarantees
            # these have no Identifications attached (nothing has been ratified yet), so
            # CASCADE on Identification.occurrence is harmless. v2 must instead reassign
            # Identification.occurrence to the keeper before deleting.
            for occ_id in old_occ_ids - {keeper.pk}:
                try:
                    Occurrence.objects.filter(id=occ_id).delete()
                    merged += 1
                except Exception as e:
                    logger.error(f"Failed to delete occurrence {occ_id}: {e}")

            keeper.save()

    new_count = Occurrence.objects.filter(detections__source_image__in=source_images).distinct().count()
    removed = existing - new_count
    if removed > 0:
        logger.info(f"Merged {merged} sibling occurrences into chain keepers (net -{removed}).")
    logger.info(
        f"Materialized {created} new occurrences across {len(source_images)} images. "
        f"Occurrences before: {existing}, after: {new_count}. Detections processed: {len(visited)}."
    )
    return {
        "occurrences_before": existing,
        "occurrences_after": new_count,
        "occurrences_created": created,
        "occurrences_merged": merged,
    }


def pair_detections(
    current_detections: list[Detection],
    next_detections: list[Detection],
    image_width: int,
    image_height: int,
    cost_threshold: float,
    algorithm: Algorithm | None,
    logger: logging.Logger,
    require_features: bool = True,
) -> int:
    """
    Greedy lowest-cost matching between two adjacent images. Sets `next_detection`
    on each detection in `current_detections` for the best partner in `next_detections`,
    if that partner's cost is below `cost_threshold` and not already claimed.

    With ``require_features=False``, detections that carry no embedding are still
    matched, on geometry alone. Returns the number of links created.
    """
    diag = image_diagonal(image_width, image_height)
    candidates: list[tuple[Detection, Detection, float]] = []

    # Cache feature lookups: one query per detection instead of O(m*n).
    if algorithm is None:
        current_vectors: dict[int, typing.Any] = {}
        next_vectors: dict[int, typing.Any] = {}
    else:
        current_vectors = {det.pk: get_feature_vector(det, algorithm) for det in current_detections}
        next_vectors = {nxt.pk: get_feature_vector(nxt, algorithm) for nxt in next_detections}

    for det in current_detections:
        det_vec = current_vectors.get(det.pk)
        if det_vec is None and require_features:
            continue
        for nxt in next_detections:
            nxt_vec = next_vectors.get(nxt.pk)
            if nxt_vec is None and require_features:
                continue
            cost = total_cost(det_vec, nxt_vec, det.bbox, nxt.bbox, diag)
            if cost < cost_threshold:
                candidates.append((det, nxt, cost))

    # Secondary keys (det.pk, nxt.pk) keep tied costs deterministic across runs.
    candidates.sort(key=lambda x: (x[2], x[0].pk, x[1].pk))

    claimed_current: set[int] = set()
    claimed_next: set[int] = set()
    links = 0

    for det, nxt, cost in candidates:
        if det.id in claimed_current or nxt.id in claimed_next:
            continue
        # Detach any existing inbound link to `nxt` before reassigning.
        try:
            prior: Detection | None = nxt.previous_detection
        except Detection.DoesNotExist:
            prior = None
        if prior is not None:
            prior.next_detection = None
            prior.save()

        det.next_detection = nxt
        det.save()
        claimed_current.add(det.id)
        claimed_next.add(nxt.id)
        links += 1
        logger.debug(f"Linked detection {det.id} -> {nxt.id} (cost {cost:.4f})")

    return links


def assign_occurrences_by_tracking_images(
    event: Event,
    logger: logging.Logger,
    algorithm: Algorithm | None,
    config: TrackingConfig,
    progress_cb: typing.Callable[[float], None] | None = None,
) -> dict[str, int]:
    source_images = list(event.captures.order_by("timestamp"))
    if len(source_images) < 2:
        logger.warning(f"Event {event.pk}: not enough images to track ({len(source_images)})")
        return {}

    transitions = len(source_images) - 1
    skipped_transitions = 0
    links = 0
    # Per-event atomic boundary: a crash mid-event rolls back chain links + occurrence
    # consolidation for THIS event only, leaving other events in the job intact.
    with transaction.atomic():
        for i in range(transitions):
            cur = source_images[i]
            nxt = source_images[i + 1]

            if not cur.width or not cur.height:
                logger.warning(
                    f"Image {cur.pk} has no dimensions; skipping transition {i + 1}/{transitions} "
                    f"for event {event.pk}."
                )
                skipped_transitions += 1
                if progress_cb:
                    progress_cb((i + 1) / transitions)
                continue

            links += pair_detections(
                list(cur.detections.all()),
                list(nxt.detections.all()),
                image_width=cur.width,
                image_height=cur.height,
                cost_threshold=config.cost_threshold,
                algorithm=algorithm,
                logger=logger,
                require_features=config.require_features,
            )
            if progress_cb:
                progress_cb((i + 1) / transitions)

        if skipped_transitions:
            logger.info(
                f"Event {event.pk}: skipped {skipped_transitions}/{transitions} transitions "
                "due to missing image dimensions."
            )

        counters = assign_occurrences_from_detection_chains(source_images, logger)

    counters["links_created"] = links
    return counters


class TrackingTask(BasePostProcessingTask):
    """
    Reconstruct occurrences by tracking detections across consecutive captures using
    feature embeddings and bbox geometry. Updates each Detection's ``next_detection``
    link and folds each chain of detections into a single Occurrence.
    """

    key = "tracking"
    name = "Occurrence Tracking"
    config_schema = TrackingConfig

    config: TrackingConfig

    def _resolve_events(self) -> list[Event]:
        """
        Return the events to track, from either scope in the config.

        A capture set is flattened to the events its images belong to. When a job is
        attached, every resolved event must belong to ``job.project``; cross-project
        IDs are dropped with a warning. That guards against a trigger smuggling event
        IDs from a project the operator cannot see.
        """
        if self.config.source_image_collection_id is not None:
            collection = SourceImageCollection.objects.filter(pk=self.config.source_image_collection_id).first()
            if collection is None:
                raise ValueError(f"Capture set {self.config.source_image_collection_id} not found.")
            qs = Event.objects.filter(captures__collections=collection).distinct()
            requested: list[int] | None = None
        else:
            requested = list(self.config.event_ids)
            qs = Event.objects.filter(pk__in=requested)

        if self.job and self.job.project_id:
            cross_project = list(qs.exclude(project_id=self.job.project_id).values_list("pk", flat=True))
            if cross_project:
                self.logger.warning(
                    f"Dropping {len(cross_project)} event(s) outside job project "
                    f"{self.job.project_id}: {cross_project}"
                )
                qs = qs.filter(project_id=self.job.project_id)

        events = list(qs.order_by("pk").distinct())
        if requested is not None:
            missing = set(requested) - {e.pk for e in events}
            if missing:
                self.logger.warning(f"Tracking requested {sorted(missing)} but those events were not found.")
        return events

    def _resolve_algorithm(self, event: Event) -> tuple[Algorithm | None, bool]:
        """Return ``(algorithm, should_track)`` for one event.

        ``algorithm`` is the feature extractor whose embeddings to compare, or None
        when the run falls back to geometry alone.
        """
        if self.config.feature_extraction_algorithm_id is not None:
            algorithm = Algorithm.objects.filter(pk=self.config.feature_extraction_algorithm_id).first()
            if algorithm is None:
                self.logger.warning(
                    f"Configured feature_extraction_algorithm_id="
                    f"{self.config.feature_extraction_algorithm_id} not found; skipping event {event.pk}."
                )
                return None, False
            return algorithm, True

        algorithm, candidates = get_unique_feature_algorithm_for_event(event)
        if algorithm is not None:
            return algorithm, True

        if candidates:
            candidate_names = [f"#{a.pk} {a.name}" for a in candidates]
            message = (
                f"Event {event.pk}: detections classified by {len(candidates)} different "
                f"feature-extraction algorithms ({candidate_names}). Pass "
                "feature_extraction_algorithm_id in the job config to disambiguate."
            )
        else:
            message = f"Event {event.pk}: no detections carry feature embeddings."

        if self.config.require_features:
            self.logger.warning(f"{message} Skipping.")
            return None, False

        self.logger.info(f"{message} Matching on bounding-box geometry alone.")
        return None, True

    def run(self) -> None:
        self.logger.info(f"Tracking starting with config: {self.config.dict()}")

        events = self._resolve_events()
        total = len(events)
        self.logger.info(f"Tracking: {total} event(s) in scope")

        totals = {"events_tracked": 0, "events_skipped": 0, "links_created": 0, "occurrences_merged": 0}

        for idx, event in enumerate(events, start=1):
            self.logger.info(f"Tracking event {idx}/{total} (id={event.pk})")

            if self.config.require_fresh_event:
                fresh, reason = event_is_fresh(event)
                if not fresh:
                    self.logger.info(
                        f"Skipping event {event.pk}: not fresh ({reason}). "
                        "v1 only handles 1:1 detection/occurrence input. "
                        "Re-tracking previously-tracked data lands in v2 (incremental)."
                    )
                    totals["events_skipped"] += 1
                    continue

            algorithm, should_track = self._resolve_algorithm(event)
            if not should_track:
                totals["events_skipped"] += 1
                continue

            if (
                self.config.skip_if_human_identifications
                and Occurrence.objects.filter(event=event, identifications__isnull=False).exists()
            ):
                self.logger.info(f"Skipping event {event.pk}: has human identifications.")
                totals["events_skipped"] += 1
                continue

            if (
                self.config.require_completely_processed_session
                and algorithm is not None
                and not event_fully_processed(event, logger=self.logger, algorithm=algorithm)
            ):
                self.logger.info(f"Skipping event {event.pk}: not fully processed.")
                totals["events_skipped"] += 1
                continue

            def _stage_progress(p: float, _idx=idx, _total=total) -> None:
                # Aggregate per-event progress into overall task progress.
                overall = ((_idx - 1) + p) / _total
                self.update_progress(overall)

            counters = assign_occurrences_by_tracking_images(
                event=event,
                logger=self.logger,
                algorithm=algorithm,
                config=self.config,
                progress_cb=_stage_progress,
            )
            totals["events_tracked"] += 1
            totals["links_created"] += counters.get("links_created", 0)
            totals["occurrences_merged"] += counters.get("occurrences_merged", 0)

        self.report_stage_metrics(
            {
                "Events tracked": totals["events_tracked"],
                "Events skipped": totals["events_skipped"],
                "Detection links created": totals["links_created"],
                "Occurrences merged": totals["occurrences_merged"],
            }
        )
        self.update_progress(1.0)
        self.logger.info(f"Tracking finished: {totals}")
