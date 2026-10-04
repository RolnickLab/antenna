import collections
import logging
import math
import typing
from collections.abc import Iterable, Iterator, Sequence

import pydantic
from django.db import transaction
from django.db.models import Count, Exists, OuterRef
from django.utils import timezone

from ami.main.models import (
    Classification,
    Detection,
    Event,
    Identification,
    Occurrence,
    SourceImage,
    SourceImageCollection,
    update_calculated_fields_for_sessions_and_stations,
    update_occurrence_determination,
)
from ami.main.models_future.track_stats import refresh_track_stats_for_ids
from ami.main.models_future.tracks import lock_sessions
from ami.ml.models import Algorithm
from ami.ml.post_processing.base import BasePostProcessingTask

COST_NOTE = (
    "The default is a starting point that is still being tuned by experiment. "
    "It suits captures taken about 20 seconds apart."
)


class TrackingConfig(pydantic.BaseModel):
    """Scope and tunables for a tracking run.

    Scope: exactly one of ``source_image_collection_id`` or ``event_ids`` says
    which sessions to track. A capture set is the bulk path; an explicit event
    list is what the Events admin page sends.

    The matching cost between two detections in consecutive captures is
    ``iou_weight * (1 - IoU) + size_weight * (1 - size ratio) + distance_weight * (distance / diagonal)``.
    Two detections are linked only when the cost is below ``cost_threshold`` and
    every enabled limit passes. The field titles and descriptions are the help text
    shown on the admin form.
    """

    source_image_collection_id: int | None = None
    event_ids: list[int] = []

    cost_threshold: float = pydantic.Field(
        1.0,
        title="Cost cutoff",
        ge=0,
        description=(
            "Two detections in neighbouring captures are only linked when their matching cost is below this "
            "value. The cost adds up how little the boxes overlap, how different their sizes are, and how far "
            "apart their centres are. Lower values link fewer detections and make fewer mistakes. " + COST_NOTE
        ),
    )
    iou_weight: float = pydantic.Field(
        1.0,
        title="Overlap weight",
        ge=0,
        description=("How strongly poor overlap between two boxes raises the cost. 0 ignores overlap. " + COST_NOTE),
    )
    size_weight: float = pydantic.Field(
        1.0,
        title="Size weight",
        ge=0,
        description=("How strongly a difference in box area raises the cost. 0 ignores size. " + COST_NOTE),
    )
    distance_weight: float = pydantic.Field(
        1.0,
        title="Distance weight",
        ge=0,
        description=(
            "How strongly the distance between box centres, measured as a share of the image diagonal, "
            "raises the cost. 0 ignores distance. " + COST_NOTE
        ),
    )

    min_iou: float | None = pydantic.Field(
        None,
        title="Minimum overlap",
        ge=0,
        le=1,
        description=(
            "Never link two detections whose boxes overlap by less than this (0 to 1, where 1 is identical "
            "boxes). Leave blank for no limit."
        ),
    )
    min_size_ratio: float | None = pydantic.Field(
        None,
        title="Minimum size ratio",
        ge=0,
        le=1,
        description=(
            "Never link two detections when the smaller box has less than this share of the area of the larger "
            "one (0 to 1). Leave blank for no limit."
        ),
    )
    max_distance: float | None = pydantic.Field(
        None,
        title="Maximum distance",
        ge=0,
        description=(
            "Never link two detections whose box centres are further apart than this share of the image "
            "diagonal (for example 0.1 is ten percent). Leave blank for no limit."
        ),
    )
    max_capture_interval_seconds: float | None = pydantic.Field(
        None,
        title="Maximum time between captures",
        gt=0,
        description=(
            "Never link detections in two neighbouring captures taken further apart than this many seconds. "
            "Leave blank for no limit."
        ),
    )

    skip_if_human_identifications: bool = pydantic.Field(
        True,
        title="Skip sessions with human identifications",
        description="Leave a session alone when someone has already identified one of its occurrences.",
    )
    require_fresh_event: bool = pydantic.Field(
        True,
        title="Only track sessions that have not been tracked",
        description=(
            "Skip a session when any of its occurrences already holds more than one detection. Turned off, a "
            "run can add links and merges to such a session, but it never undoes earlier ones."
        ),
    )

    @pydantic.root_validator(skip_on_failure=True)
    def _exactly_one_scope(cls, values: dict) -> dict:
        scopes = [values.get("source_image_collection_id"), values.get("event_ids") or None]
        if sum(s is not None for s in scopes) != 1:
            raise ValueError("Provide exactly one of source_image_collection_id or event_ids")
        return values

    class Config:
        extra = "forbid"


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


def captures_too_far_apart(first: SourceImage, second: SourceImage, config: TrackingConfig) -> bool:
    """Is the gap between two captures over the interval limit? A missing timestamp counts as too far."""
    if config.max_capture_interval_seconds is None:
        return False
    if first.timestamp is None or second.timestamp is None:
        return True
    return abs((second.timestamp - first.timestamp).total_seconds()) > config.max_capture_interval_seconds


def event_is_fresh(event: Event) -> tuple[bool, str]:
    """Has this event's detections already been grouped into chains?

    The guard keeps tracking away from events that were already consolidated: merging
    those again can delete an occurrence that carries identifications. An occurrence
    spanning more than one detection is the signal for that.

    A detection with no occurrence at all is not that signal, since the chain walk creates an
    occurrence for a chain that has none. Occurrences are found through their detections'
    captures, not ``Occurrence.event``, so one that reaches into this session from another
    session also counts.
    """
    multi_detection_occurrences = (
        Occurrence.objects.filter(pk__in=Detection.objects.filter(source_image__event=event).values("occurrence_id"))
        .annotate(_n=Count("detections"))
        .filter(_n__gt=1)
        .count()
    )
    if multi_detection_occurrences:
        return False, f"{multi_detection_occurrences} occurrence(s) already span >1 detection"
    return True, ""


def processed_captures(event: Event) -> list[SourceImage]:
    """Captures of a session that have at least one detection row, oldest first.

    A null-bbox marker row counts: it records that a capture was processed and found nothing.
    Captures nobody processed are left out, so they cannot break the adjacency of their neighbours.
    """
    return list(
        SourceImage.objects.filter(event=event)
        .filter(Exists(Detection.objects.filter(source_image=OuterRef("pk"))))
        .order_by("timestamp", "pk")
    )


def record_tracking_determination(occurrence: Occurrence, algorithm: Algorithm) -> Classification | None:
    """Leave a terminal classification by the tracking algorithm after a merge changed the determination.

    The row carries the winning prediction and points back at it through ``applied_to``, the way
    class masking does, so the history shows what tracking decided. Nothing is written when the
    winner already came from the tracking algorithm.
    """
    winner = occurrence.best_prediction
    if winner is None or winner.detection_id is None or winner.taxon_id is None:
        return None
    if winner.algorithm_id == algorithm.pk:
        return None
    return Classification.objects.create(
        detection=winner.detection,
        taxon=winner.taxon,
        score=winner.score,
        terminal=True,
        algorithm=algorithm,
        timestamp=timezone.now(),
        applied_to=winner,
    )


def assign_occurrences_from_detection_chains(
    source_images: Sequence[SourceImage], logger: logging.Logger, record_as: Algorithm | None = None
) -> dict[str, int]:
    """Fold each chain of linked detections into one occurrence, keeping the first existing one.

    A chain never leaves the given captures, which belong to one session, so a link that crosses a
    session boundary starts a new chain on each side. Identifications move onto the keeper before the
    occurrences that held them are deleted, because deleting an occurrence deletes its identifications.
    With ``record_as`` set, a merge that changes the keeper's determination leaves a classification by
    that algorithm. Statistics are stored for every occurrence the chains settle on.
    """
    image_ids = [image.pk for image in source_images]
    detections = list(
        Detection.objects.valid().filter(source_image_id__in=image_ids).select_related("source_image", "occurrence")
    )
    by_id = {det.pk: det for det in detections}
    # Walk each capture in time order, so a chain starts at its earliest detection.
    position = {image_id: i for i, image_id in enumerate(image_ids)}
    detections.sort(key=lambda d: (position[d.source_image_id], d.pk))
    has_previous = {det.next_detection_id for det in detections if det.next_detection_id in by_id}

    visited: set[int] = set()
    settled: set[int] = set()
    created = merged = identifications_moved = determinations_recorded = 0
    existing = Occurrence.objects.filter(detections__source_image_id__in=image_ids).distinct().count()

    for det in detections:
        if det.pk in visited or det.pk in has_previous:
            continue
        chain: list[Detection] = []
        current: Detection | None = det
        while current is not None and current.pk not in visited:
            chain.append(current)
            visited.add(current.pk)
            current = by_id.get(current.next_detection_id) if current.next_detection_id else None

        old_occ_ids = {d.occurrence_id for d in chain if d.occurrence_id}
        # Coherent chains need no change but still get their statistics stored below.
        if len(old_occ_ids) == 1 and all(d.occurrence_id is not None for d in chain):
            settled.update(old_occ_ids)
            continue

        keeper: Occurrence | None = next((d.occurrence for d in chain if d.occurrence_id), None)
        previous_determination_id = keeper.determination_id if keeper is not None else None
        if keeper is None:
            first_image = chain[0].source_image
            keeper = Occurrence.objects.create(
                event=first_image.event, deployment=first_image.deployment, project=first_image.project
            )
            created += 1

        for d in chain:
            if d.occurrence_id != keeper.pk:
                d.occurrence = keeper
                d.save(update_fields=["occurrence"])

        doomed = old_occ_ids - {keeper.pk}
        if doomed:
            identifications_moved += Identification.objects.filter(occurrence_id__in=doomed).update(occurrence=keeper)
            Occurrence.objects.filter(pk__in=doomed).delete()
            merged += len(doomed)

        # Only the determination is written, so a column this run did not change keeps its stored value.
        if update_occurrence_determination(keeper, save=False):
            keeper.save(update_determination=False, update_fields=["determination", "determination_score"])
        if record_as is not None and keeper.determination_id != previous_determination_id:
            if record_tracking_determination(keeper, record_as) is not None:
                determinations_recorded += 1
        settled.add(keeper.pk)

    # Stored once every determination is settled, since id_agreement is measured against it.
    stats_stored = refresh_track_stats_for_ids(settled)

    new_count = Occurrence.objects.filter(detections__source_image_id__in=image_ids).distinct().count()
    logger.info(
        f"Created {created} occurrences and merged {merged} across {len(image_ids)} captures "
        f"(occurrences before: {existing}, after: {new_count}). Moved {identifications_moved} identification(s), "
        f"recorded {determinations_recorded} determination change(s), stored statistics for {stats_stored}."
    )
    return {
        "occurrences_before": existing,
        "occurrences_after": new_count,
        "occurrences_created": created,
        "occurrences_merged": merged,
        "identifications_moved": identifications_moved,
        "determinations_recorded": determinations_recorded,
    }


def select_links(
    current_detections: Sequence[Detection],
    next_detections: Sequence[Detection],
    diag: float,
    config: TrackingConfig,
) -> list[tuple[Detection, Detection, float]]:
    """The links to make between two adjacent captures, lowest cost first; nothing is saved.

    A pair is a candidate when it passes every enabled limit and its cost is below the cutoff.
    Candidates are taken lowest cost first, and each detection is linked at most once on either side.
    """
    candidates: list[tuple[Detection, Detection, float]] = []
    for det in current_detections:
        for nxt in next_detections:
            cost = pair_cost(det.bbox, nxt.bbox, diag, config)
            if cost is not None and cost < config.cost_threshold:
                candidates.append((det, nxt, cost))

    # Secondary keys keep tied costs deterministic across runs.
    candidates.sort(key=lambda x: (x[2], x[0].pk, x[1].pk))

    claimed_current: set[int] = set()
    claimed_next: set[int] = set()
    links: list[tuple[Detection, Detection, float]] = []
    for det, nxt, cost in candidates:
        if det.pk in claimed_current or nxt.pk in claimed_next:
            continue
        claimed_current.add(det.pk)
        claimed_next.add(nxt.pk)
        links.append((det, nxt, cost))
    return links


def save_links(links: Iterable[tuple[Detection, Detection, float]], logger: logging.Logger) -> None:
    """Store each link as ``next_detection``, first detaching any other detection that points at the target."""
    links = list(links)
    if not links:
        return
    Detection.objects.filter(next_detection_id__in=[nxt.pk for _, nxt, _ in links]).update(next_detection=None)
    for det, nxt, cost in links:
        det.next_detection = nxt
        logger.debug(f"Linked detection {det.pk} -> {nxt.pk} (cost {cost:.4f})")
    Detection.objects.bulk_update([det for det, _, _ in links], ["next_detection"])


def iter_transition_links(
    source_images: Sequence[SourceImage], config: TrackingConfig, logger: logging.Logger
) -> Iterator[list[tuple[Detection, Detection, float]] | None]:
    """Yield the proposed links for each pair of consecutive captures, in order, saving nothing.

    Yields None for a transition that is not compared (the earlier capture has no dimensions) and an
    empty list for one over the interval limit.
    """
    transitions = len(source_images) - 1
    for i in range(transitions):
        cur, nxt = source_images[i], source_images[i + 1]
        if captures_too_far_apart(cur, nxt, config):
            yield []
            continue
        if not cur.width or not cur.height:
            logger.warning(f"Capture {cur.pk} has no dimensions; not comparing it with the next capture.")
            yield None
            continue
        yield select_links(
            list(cur.detections.valid()),
            list(nxt.detections.valid()),
            image_diagonal(cur.width, cur.height),
            config,
        )


def assign_occurrences_by_tracking_images(
    event: Event,
    logger: logging.Logger,
    config: TrackingConfig,
    progress_cb: typing.Callable[[float], None] | None = None,
    record_as: Algorithm | None = None,
) -> dict[str, int]:
    """Link the detections of one session's processed captures and fold the chains into occurrences."""
    source_images = processed_captures(event)
    if len(source_images) < 2:
        logger.warning(f"Session {event.pk}: fewer than two processed captures ({len(source_images)}).")
        return {}

    transitions = len(source_images) - 1
    links = skipped_for_dimensions = 0
    skipped_for_interval = sum(
        captures_too_far_apart(source_images[i], source_images[i + 1], config) for i in range(transitions)
    )
    # Per-session atomic boundary: a crash mid-session rolls back this session only.
    with transaction.atomic():
        for i, proposed in enumerate(iter_transition_links(source_images, config, logger)):
            if proposed is None:
                skipped_for_dimensions += 1
            else:
                save_links(proposed, logger)
                links += len(proposed)
            if progress_cb:
                progress_cb((i + 1) / transitions)
        counters = assign_occurrences_from_detection_chains(source_images, logger, record_as=record_as)

    counters["links_created"] = links
    counters["transitions_too_far_apart"] = skipped_for_interval
    counters["transitions_without_dimensions"] = skipped_for_dimensions
    return counters


def nothing_tracked_summary(skip_reasons: collections.Counter[str]) -> str:
    """The line a job shows when every session in scope was skipped, with the count per reason."""
    total = sum(skip_reasons.values())
    reasons = "; ".join(f"{count} because {reason}" for reason, count in skip_reasons.most_common())
    return f"Nothing was tracked: {total} session(s) skipped ({reasons})."


class TrackingTask(BasePostProcessingTask):
    """Link detections across consecutive processed captures and fold each chain into one occurrence.

    Sets each detection's ``next_detection`` link from bounding-box overlap, size and distance,
    then merges every chain into a single occurrence per session.
    """

    key = "tracking"
    name = "Occurrence tracking"
    config_schema = TrackingConfig

    config: TrackingConfig

    def _resolve_events(self) -> list[Event]:
        """Return the sessions to track, from either scope in the config.

        When a job is attached, sessions outside ``job.project`` are dropped with a warning, which
        guards against a trigger smuggling in sessions from a project the operator cannot see.
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
                    f"Dropping {len(cross_project)} session(s) outside job project "
                    f"{self.job.project_id}: {cross_project}"
                )
                qs = qs.filter(project_id=self.job.project_id)

        events = list(qs.order_by("pk").distinct())
        if requested is not None:
            missing = set(requested) - {e.pk for e in events}
            if missing:
                self.logger.warning(f"Tracking requested {sorted(missing)} but those sessions were not found.")
        return events

    def _skip_reason(self, event: Event) -> str | None:
        """Why this session must not be tracked, or None. Called under the session lock."""
        if self.config.require_fresh_event:
            fresh, detail = event_is_fresh(event)
            if not fresh:
                self.logger.info(f"Skipping session {event.pk}: already tracked or edited ({detail}).")
                return "it was already tracked or edited"
        if (
            self.config.skip_if_human_identifications
            and Occurrence.objects.filter(event=event, identifications__isnull=False).exists()
        ):
            self.logger.info(f"Skipping session {event.pk}: has human identifications.")
            return "it has human identifications"
        return None

    def run(self) -> None:
        self.logger.info(f"Tracking starting with config: {self.config.dict()}")

        events = self._resolve_events()
        total = len(events)
        self.logger.info(f"Tracking: {total} session(s) in scope")

        totals: collections.Counter[str] = collections.Counter()
        tracked_event_ids: list[int] = []
        # Why each session was skipped, so a run that tracks nothing can say so.
        skip_reasons: collections.Counter[str] = collections.Counter()

        for idx, event in enumerate(events, start=1):
            self.logger.info(f"Tracking session {idx}/{total} (id={event.pk})")
            # The checks and the writes share one lock on the session, so an edit made since the
            # job started is seen and an edit made during the run waits.
            with transaction.atomic():
                lock_sessions([event.pk])
                reason = self._skip_reason(event)
                if reason is not None:
                    totals["skipped"] += 1
                    skip_reasons[reason] += 1
                    continue

                def _stage_progress(p: float, _idx=idx, _total=total) -> None:
                    self.update_progress(((_idx - 1) + p) / _total)

                counters = assign_occurrences_by_tracking_images(
                    event=event,
                    logger=self.logger,
                    config=self.config,
                    record_as=self.algorithm,
                    progress_cb=_stage_progress,
                )
                if not counters:
                    totals["skipped"] += 1
                    skip_reasons["it has fewer than two processed captures"] += 1
                    continue
                totals["tracked"] += 1
                tracked_event_ids.append(event.pk)
                for key in ("links_created", "occurrences_merged", "transitions_too_far_apart"):
                    totals[key] += counters.get(key, 0)

        # Merging occurrences changes the session and station counts, which no save refreshes.
        # This already runs in a background job, so the station refresh stays inline.
        update_calculated_fields_for_sessions_and_stations(tracked_event_ids, stations_async=False)

        metrics: dict[str, typing.Any] = {
            "Sessions tracked": totals["tracked"],
            "Sessions skipped": totals["skipped"],
            "Detection links created": totals["links_created"],
            "Occurrences merged": totals["occurrences_merged"],
        }
        if self.config.max_capture_interval_seconds is not None:
            metrics["Capture pairs too far apart to compare"] = totals["transitions_too_far_apart"]
        # The job still succeeds when every session is skipped, so this line is written on every run:
        # a retry keeps text params, and a stale line would contradict the counts.
        if totals["tracked"]:
            metrics["Result"] = f"Tracked {totals['tracked']} session(s)."
        elif skip_reasons:
            metrics["Result"] = nothing_tracked_summary(skip_reasons)
            self.logger.warning(metrics["Result"])
        else:
            metrics["Result"] = "Nothing was tracked: no sessions in scope."
        self.report_stage_metrics(metrics)
        self.update_progress(1.0)
        self.logger.info(f"Tracking finished: {dict(totals)}")
