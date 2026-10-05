"""The tracking post-processing task: links detections across consecutive captures and merges each chain.

The matching rules live in ``matching.py`` and the settings in ``config.py``, both free of Django;
this module reads and writes the database around them.
"""

import collections
import logging
import typing
from collections.abc import Iterable, Iterator, Sequence

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
from ami.ml.models import Algorithm
from ami.ml.post_processing.base import BasePostProcessingTask

from .config import TrackingConfig
from .matching import captures_too_far_apart, image_diagonal, select_links
from .sessions import lock_sessions


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
    that algorithm.
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

    new_count = Occurrence.objects.filter(detections__source_image_id__in=image_ids).distinct().count()
    logger.info(
        f"Created {created} occurrences and merged {merged} across {len(image_ids)} captures "
        f"(occurrences before: {existing}, after: {new_count}). Moved {identifications_moved} identification(s), "
        f"recorded {determinations_recorded} determination change(s)."
    )
    return {
        "occurrences_before": existing,
        "occurrences_after": new_count,
        "occurrences_created": created,
        "occurrences_merged": merged,
        "identifications_moved": identifications_moved,
        "determinations_recorded": determinations_recorded,
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
        if captures_too_far_apart(cur.timestamp, nxt.timestamp, config):
            yield []
            continue
        if not cur.width or not cur.height:
            logger.warning(f"Capture {cur.pk} has no dimensions; not comparing it with the next capture.")
            yield None
            continue
        current = {det.pk: det for det in cur.detections.valid()}
        following = {det.pk: det for det in nxt.detections.valid()}
        links = select_links(
            [(pk, det.bbox) for pk, det in current.items()],
            [(pk, det.bbox) for pk, det in following.items()],
            image_diagonal(cur.width, cur.height),
            config,
        )
        yield [(current[from_id], following[to_id], cost) for from_id, to_id, cost in links]


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
        captures_too_far_apart(source_images[i].timestamp, source_images[i + 1].timestamp, config)
        for i in range(transitions)
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
