"""The tracking post-processing task: links detections across consecutive captures and merges each chain.

The matching rules live in ``matching.py`` and the settings in ``config.py``, both free of Django;
this module reads and writes the database around them.
"""

import collections
import dataclasses
import logging
import time
import typing
from collections.abc import Iterable, Iterator, Sequence

from django.db import transaction
from django.db.models import Count, Exists, OuterRef

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
from ami.ml.models import Algorithm, AlgorithmResult
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.post_processing.base import BasePostProcessingTask

from .config import TrackingConfig
from .matching import captures_too_far_apart, image_diagonal, select_links
from .sessions import lock_sessions
from .stats import occurrence_figures

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job


# Progress is saved after this many matched transitions, or after this many seconds, whichever comes first.
PROGRESS_EVERY_TRANSITIONS = 25
PROGRESS_EVERY_SECONDS = 5.0


@dataclasses.dataclass
class LinkedOccurrence:
    """An occurrence the run built from a chain of two or more detections, or by merging occurrences."""

    keeper: Occurrence
    detections: list[Detection]
    determination_before_id: int | None
    merged_ids: list[int]
    link_costs: list[float]


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


def record_tracking_results(
    linked: Sequence[LinkedOccurrence], algorithm: Algorithm, job: "Job | None"
) -> dict[int, AlgorithmResult]:
    """Write one tracking result per linked occurrence, keyed by occurrence id.

    The figures are computed in memory from the chains' detections plus one query for their terminal
    classifications. Only machine labels count: classifications by post-processing algorithms (size filter,
    class masking) are left out, and a classification with no algorithm counts as a source label.
    Call after the determinations have settled.
    """
    if not linked:
        return {}
    detection_ids = [d.pk for item in linked for d in item.detections]
    labels: dict[int, list[int | None]] = collections.defaultdict(list)
    for detection_id, taxon_id in (
        Classification.objects.filter(detection_id__in=detection_ids, terminal=True)
        .exclude(algorithm__task_type=AlgorithmTaskType.POST_PROCESSING.value)
        .values_list("detection_id", "taxon_id")
    ):
        labels[detection_id].append(taxon_id)

    results = []
    for item in linked:
        figures = occurrence_figures(
            boxes=[d.bbox for d in item.detections],
            sizes=[(d.source_image.width, d.source_image.height) for d in item.detections],
            labels=[label for d in item.detections for label in labels.get(d.pk, [])],
            determination_id=item.keeper.determination_id,
        )
        results.append(
            AlgorithmResult(
                occurrence=item.keeper,
                algorithm=algorithm,
                job=job,
                kind=AlgorithmResult.Kind.TRACKING,
                value=figures.motion,
                data={
                    **dataclasses.asdict(figures),
                    "link_costs": item.link_costs,
                    "determination_before_id": item.determination_before_id,
                    "determination_after_id": item.keeper.determination_id,
                    "merged_occurrence_ids": item.merged_ids,
                },
            )
        )
    return {result.occurrence_id: result for result in AlgorithmResult.objects.record_many(results)}


def assign_occurrences_from_detection_chains(
    source_images: Sequence[SourceImage],
    logger: logging.Logger,
    record_as: Algorithm | None = None,
    job: "Job | None" = None,
    link_costs: dict[int, float] | None = None,
) -> dict[str, int]:
    """Fold each chain of linked detections into one occurrence, keeping the first existing one.

    A chain never leaves the given captures, which belong to one session, so a link that crosses a
    session boundary starts a new chain on each side. Identifications move onto the keeper before the
    occurrences that held them are deleted, because deleting an occurrence deletes its identifications.
    Results of the absorbed occurrences move onto the keeper first. With ``record_as`` set, every keeper
    built from two or more detections or from a merge gets a tracking result attributed to ``job``, which
    records the determination before and after, so no classification is written for it. ``link_costs`` maps a
    detection to the cost of its link to the next one, for the links this run made.
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
    created = merged = identifications_moved = 0
    linked: dict[int, LinkedOccurrence] = {}
    deleted: set[int] = set()
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
        # A chain already held by exactly one occurrence needs no change.
        if len(old_occ_ids) == 1 and all(d.occurrence_id is not None for d in chain):
            continue

        keeper: Occurrence | None = next((d.occurrence for d in chain if d.occurrence_id), None)
        previous_determination_id = keeper.determination_id if keeper is not None else None
        if keeper is None:
            first_image = chain[0].source_image
            keeper = Occurrence.objects.create(
                event=first_image.event, deployment=first_image.deployment, project=first_image.project
            )
            created += 1

        moving = [d for d in chain if d.occurrence_id != keeper.pk]
        if moving:
            Detection.objects.filter(pk__in=[d.pk for d in moving]).update(occurrence=keeper)
            for d in moving:
                d.occurrence = keeper

        doomed = old_occ_ids - {keeper.pk}
        if doomed:
            identifications_moved += Identification.objects.filter(occurrence_id__in=doomed).update(occurrence=keeper)
            # Deleting an occurrence deletes its results, so they move onto the keeper first.
            AlgorithmResult.objects.move_to_occurrence(keeper, doomed)
            Occurrence.objects.filter(pk__in=doomed).delete()
            deleted |= doomed
            merged += len(doomed)

        # Only the determination is written, so a column this run did not change keeps its stored value.
        if update_occurrence_determination(keeper, save=False):
            keeper.save(update_determination=False, update_fields=["determination", "determination_score"])
        if record_as is not None and (len(chain) > 1 or doomed):
            costs = [round(link_costs[d.pk], 4) for d in chain[:-1] if d.pk in link_costs]
            linked[keeper.pk] = LinkedOccurrence(keeper, chain, previous_determination_id, sorted(doomed), costs)

    results: dict[int, AlgorithmResult] = {}
    if record_as is not None:
        # A keeper that a later chain absorbed no longer exists.
        final = [item for pk, item in linked.items() if pk not in deleted]
        results = record_tracking_results(final, record_as, job)

    new_count = Occurrence.objects.filter(detections__source_image_id__in=image_ids).distinct().count()
    logger.info(
        f"Created {created} occurrences and merged {merged} across {len(image_ids)} captures "
        f"(occurrences before: {existing}, after: {new_count}). Moved {identifications_moved} identification(s), "
        f"recorded {len(results)} result(s)."
    )
    return {
        "occurrences_before": existing,
        "occurrences_after": new_count,
        "occurrences_created": created,
        "occurrences_merged": merged,
        "identifications_moved": identifications_moved,
        "results_recorded": len(results),
    }


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


@dataclasses.dataclass
class SessionPlan:
    """The links proposed for one session, computed without writing anything.

    ``snapshot`` records each detection's ``next_detection`` and occurrence as they were read, so the
    write phase can tell whether the session changed while the links were being matched.
    """

    source_images: list[SourceImage]
    snapshot: dict[int, tuple[int | None, int | None]]
    proposals: list[list[tuple[Detection, Detection, float]] | None]
    transitions_too_far_apart: int


def iter_transition_links(
    source_images: Sequence[SourceImage],
    detections_by_capture: dict[int, dict[int, Detection]],
    config: TrackingConfig,
    logger: logging.Logger,
) -> Iterator[list[tuple[Detection, Detection, float]] | None]:
    """Yield the proposed links for each pair of consecutive captures, in order, saving nothing.

    Yields None for a transition that is not compared (the earlier capture has no dimensions) and an
    empty list for one over the interval limit.
    """
    for i in range(len(source_images) - 1):
        cur, nxt = source_images[i], source_images[i + 1]
        if captures_too_far_apart(cur.timestamp, nxt.timestamp, config):
            yield []
            continue
        if not cur.width or not cur.height:
            logger.warning(f"Capture {cur.pk} has no dimensions; not comparing it with the next capture.")
            yield None
            continue
        current = detections_by_capture.get(cur.pk, {})
        following = detections_by_capture.get(nxt.pk, {})
        links = select_links(
            [(pk, det.bbox) for pk, det in current.items()],
            [(pk, det.bbox) for pk, det in following.items()],
            image_diagonal(cur.width, cur.height),
            config,
        )
        yield [(current[from_id], following[to_id], cost) for from_id, to_id, cost in links]


def plan_session_links(
    event: Event,
    logger: logging.Logger,
    config: TrackingConfig,
    progress_cb: typing.Callable[[float], None] | None = None,
) -> SessionPlan | None:
    """Match the detections of one session's processed captures, writing nothing and holding no lock.

    Returns None when the session has fewer than two processed captures. ``progress_cb`` receives the
    share of transitions matched after each one.
    """
    source_images = processed_captures(event)
    if len(source_images) < 2:
        logger.warning(f"Session {event.pk}: fewer than two processed captures ({len(source_images)}).")
        return None
    detections_by_capture: dict[int, dict[int, Detection]] = collections.defaultdict(dict)
    for det in Detection.objects.valid().filter(source_image_id__in=[image.pk for image in source_images]):
        detections_by_capture[det.source_image_id][det.pk] = det
    snapshot = {
        det.pk: (det.next_detection_id, det.occurrence_id)
        for detections in detections_by_capture.values()
        for det in detections.values()
    }
    transitions = len(source_images) - 1
    proposals = []
    for i, proposed in enumerate(iter_transition_links(source_images, detections_by_capture, config, logger)):
        proposals.append(proposed)
        if progress_cb:
            progress_cb((i + 1) / transitions)
    too_far = sum(
        captures_too_far_apart(source_images[i].timestamp, source_images[i + 1].timestamp, config)
        for i in range(transitions)
    )
    return SessionPlan(source_images, snapshot, proposals, too_far)


def plan_is_current(plan: SessionPlan) -> bool:
    """Whether the session's detections still have the links and occurrences the plan was matched against."""
    current = {
        pk: (next_id, occurrence_id)
        for pk, next_id, occurrence_id in Detection.objects.valid()
        .filter(source_image_id__in=[image.pk for image in plan.source_images])
        .values_list("pk", "next_detection_id", "occurrence_id")
    }
    return current == plan.snapshot


def write_session_plan(
    plan: SessionPlan,
    logger: logging.Logger,
    record_as: Algorithm | None = None,
    job: "Job | None" = None,
) -> dict[str, int]:
    """Save a plan's links and fold the chains into occurrences.

    Call inside the session's transaction, after checking ``plan_is_current``. It does no progress
    writes, since saving the job inside the transaction would keep its row locked.
    """
    links = skipped_for_dimensions = 0
    costs: dict[int, float] = {}
    for proposed in plan.proposals:
        if proposed is None:
            skipped_for_dimensions += 1
            continue
        save_links(proposed, logger)
        links += len(proposed)
        costs.update({det.pk: cost for det, _, cost in proposed})
    counters = assign_occurrences_from_detection_chains(
        plan.source_images, logger, record_as=record_as, job=job, link_costs=costs
    )
    counters["links_created"] = links
    counters["transitions_too_far_apart"] = plan.transitions_too_far_apart
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

    def _track_session(self, event: Event, progress_cb: typing.Callable[[float], None] | None = None):
        """Track one session in two phases, returning ``(counters, None)`` or ``(None, skip reason)``.

        Matching reads only and runs outside any transaction, so the job can keep saving progress
        while it works. Writing is one short transaction that locks the session, repeats the guards,
        and refuses to write when the session changed since it was matched.
        """
        if self._skip_reason(event) is not None:
            plan = None  # the locked check below reports the reason
        else:
            plan = plan_session_links(event, self.logger, self.config, progress_cb)
        with transaction.atomic():
            lock_sessions([event.pk])
            reason = self._skip_reason(event)
            if reason is not None:
                return None, reason
            if plan is None:
                return None, "it has fewer than two processed captures"
            if not plan_is_current(plan):
                self.logger.warning(f"Skipping session {event.pk}: it changed while its links were being matched.")
                return None, "it changed while it was being tracked"
            counters = write_session_plan(plan, self.logger, record_as=self.algorithm, job=self.job)
        return counters, None

    def _throttled_progress(self, index: int, total: int) -> typing.Callable[[float], None]:
        """A callback that saves progress for session ``index`` of ``total`` every few transitions or seconds."""
        last_saved = time.monotonic()
        matched = 0

        def report(share: float) -> None:
            nonlocal last_saved, matched
            matched += 1
            if matched % PROGRESS_EVERY_TRANSITIONS == 0 or time.monotonic() - last_saved >= PROGRESS_EVERY_SECONDS:
                self.update_progress(((index - 1) + share) / total)
                last_saved = time.monotonic()

        return report

    def run(self) -> None:
        """Track every session in scope, matching outside a transaction and writing in one short one per session.

        Matching saves job progress as it goes, because the stale-job reaper revokes a job whose
        ``updated_at`` stops moving and a busy session can take minutes. Saving inside the write
        transaction would not help: it stays invisible until commit and locks the job row.

        A capture-set scope tracks every processed capture of the sessions the set touches, not only the
        captures in the set, because a chain needs the captures between its detections. A session that
        fails is rolled back, logged and counted, and the run goes on with the next one. After the counts
        of the sessions that were tracked are refreshed and the metrics reported, the run raises if any
        session failed, so the job is marked failed.
        """
        self.logger.info(f"Tracking starting with config: {self.config.dict()}")

        events = self._resolve_events()
        total = len(events)
        self.logger.info(f"Tracking: {total} session(s) in scope")

        totals: collections.Counter[str] = collections.Counter()
        tracked_event_ids: list[int] = []
        failed_event_ids: list[int] = []
        # Why each session was skipped, so a run that tracks nothing can say so.
        skip_reasons: collections.Counter[str] = collections.Counter()

        for idx, event in enumerate(events, start=1):
            self.logger.info(f"Tracking session {idx}/{total} (id={event.pk})")
            try:
                counters, reason = self._track_session(event, self._throttled_progress(idx, total))
            except Exception:
                self.logger.exception(f"Tracking failed for session {event.pk}; its changes were rolled back.")
                failed_event_ids.append(event.pk)
                counters, reason = None, None
            if counters is not None:
                totals["tracked"] += 1
                tracked_event_ids.append(event.pk)
                for key in ("links_created", "occurrences_merged", "results_recorded", "transitions_too_far_apart"):
                    totals[key] += counters.get(key, 0)
            elif reason is not None:
                totals["skipped"] += 1
                skip_reasons[reason] += 1
            # Saved between sessions, after the transaction has committed, so the bar moves per session.
            self.update_progress(idx / total)

        # Merging occurrences changes the session and station counts, which no save refreshes.
        # This already runs in a background job, so the station refresh stays inline.
        update_calculated_fields_for_sessions_and_stations(tracked_event_ids, stations_async=False)

        metrics: dict[str, typing.Any] = {
            "Sessions tracked": totals["tracked"],
            "Sessions skipped": totals["skipped"],
            "Sessions failed": len(failed_event_ids),
            "Detection links created": totals["links_created"],
            "Occurrences merged": totals["occurrences_merged"],
            "Occurrences recorded": totals["results_recorded"],
        }
        if self.config.max_capture_interval_seconds is not None:
            metrics["Capture pairs too far apart to compare"] = totals["transitions_too_far_apart"]
        # The job still succeeds when every session is skipped, so this line is written on every run:
        # a retry keeps text params, and a stale line would contradict the counts.
        if failed_event_ids:
            metrics["Result"] = (
                f"Tracking failed for {len(failed_event_ids)} of {total} session(s) "
                f"(ids {failed_event_ids}); {totals['tracked']} were tracked."
            )
        elif totals["tracked"]:
            metrics["Result"] = f"Tracked {totals['tracked']} session(s)."
        elif skip_reasons:
            metrics["Result"] = nothing_tracked_summary(skip_reasons)
            self.logger.warning(metrics["Result"])
        else:
            metrics["Result"] = "Nothing was tracked: no sessions in scope."
        self.report_stage_metrics(metrics)
        self.update_progress(1.0)
        self.logger.info(f"Tracking finished: {dict(totals)}")
        if failed_event_ids:
            raise RuntimeError(metrics["Result"])
