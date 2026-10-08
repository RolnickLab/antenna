"""The tracking post-processing task: links detections in consecutive captures and merges the occurrences they join.

The matching rules live in ``matching.py``, the settings in ``config.py`` and the merge plan in
``chains.py``, all free of Django; this module reads and writes the database around them.
"""

import collections
import dataclasses
import logging
import time
import typing
from collections.abc import Iterator, Sequence

from cachalot.api import cachalot_disabled
from django.db import connection, transaction
from django.db.models import Count, Exists, F, OuterRef

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
from ami.ml.post_processing.base import BasePostProcessingTask

from .chains import MergeGroup, merge_groups
from .config import TrackingConfig
from .matching import captures_too_far_apart, image_diagonal, select_links
from .results import TrackingResultData
from .sessions import lock_sessions
from .stats import Label, occurrence_figures

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job


# Progress is saved after this many matched transitions, or after this many seconds, whichever comes first.
PROGRESS_EVERY_TRANSITIONS = 25
PROGRESS_EVERY_SECONDS = 5.0
# Rows per statement when occurrence determinations are written in bulk.
WRITE_BATCH_SIZE = 1000

Link = tuple[int, int, float]


class SkipSession(Exception):
    """Raised with the reason a session is not tracked; the job counts sessions by reason."""


def session_has_links(event: Event) -> bool:
    """Whether a detection in this session already links to a next one, which marks a session as tracked."""
    return Detection.objects.filter(source_image__event=event, next_detection__isnull=False).exists()


def session_has_identifications(event: Event) -> bool:
    """Whether someone has identified an occurrence that holds a detection in this session."""
    return Identification.objects.filter(occurrence__detections__source_image__event=event).exists()


def processed_captures(event: Event) -> list[SourceImage]:
    """Captures of a session that have at least one detection row and a timestamp, oldest first.

    A null-bbox marker row counts: it records that a capture was processed and found nothing.
    Captures nobody processed are left out, so they cannot break the adjacency of their neighbours,
    and so are captures with no timestamp, whose place in the sequence is unknown.
    """
    return list(
        SourceImage.objects.filter(event=event, timestamp__isnull=False)
        .filter(Exists(Detection.objects.filter(source_image=OuterRef("pk"))))
        .order_by("timestamp", "pk")
    )


@dataclasses.dataclass
class SessionPlan:
    """What a run would change in one session, worked out without writing anything.

    ``snapshot`` records each detection's ``next_detection`` and occurrence as they were read, so the
    write phase can tell whether the session changed while the links were being matched.
    """

    event: Event
    source_images: list[SourceImage]
    detection_algorithm_id: int | None
    detections: dict[int, Detection]
    snapshot: dict[int, tuple[int | None, int | None]]
    links: list[Link]
    groups: list[MergeGroup]
    transitions_too_far_apart: int
    transitions_without_dimensions: int

    def occurrence_ids(self) -> set[int]:
        return {occurrence_id for _, occurrence_id in self.snapshot.values() if occurrence_id is not None}


def iter_transition_links(
    source_images: Sequence[SourceImage],
    detections_by_capture: dict[int, list[Detection]],
    config: TrackingConfig,
    logger: logging.Logger,
) -> Iterator[list[Link] | None]:
    """Yield the proposed links for each pair of consecutive captures, in order, saving nothing.

    A detection that already links to a next one is not a candidate to link from, and one that an
    earlier link already points at is not a candidate to link to, so a run never replaces a link.
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
        links = select_links(
            [(d.pk, d.bbox) for d in detections_by_capture.get(cur.pk, []) if d.next_detection_id is None],
            [(d.pk, d.bbox) for d in detections_by_capture.get(nxt.pk, []) if not d.has_previous],
            image_diagonal(cur.width, cur.height),
            config,
        )
        yield list(links)


def session_detections(source_images: Sequence[SourceImage], detection_algorithm_id: int | None) -> list[Detection]:
    """The detections tracking compares on these captures: those with a box, from one detector when one is given."""
    qs = Detection.objects.valid().filter(source_image_id__in=[image.pk for image in source_images])
    if detection_algorithm_id is not None:
        qs = qs.filter(detection_algorithm_id=detection_algorithm_id)
    return list(qs.annotate(has_previous=Exists(Detection.objects.filter(next_detection_id=OuterRef("pk")))))


def plan_session_links(
    event: Event,
    logger: logging.Logger,
    config: TrackingConfig,
    progress_cb: typing.Callable[[float], None] | None = None,
) -> SessionPlan:
    """Match one session's processed captures and work out the merges, writing nothing and holding no lock.

    Raises ``SkipSession`` when the session has fewer than two processed captures, or when no detector
    was chosen and its detections come from more than one. Two detectors find the same insect twice,
    and their boxes would be linked into parallel chains. ``progress_cb`` receives the share of
    transitions matched after each one.
    """
    source_images = processed_captures(event)
    if len(source_images) < 2:
        raise SkipSession("it has fewer than two processed captures")
    detections = session_detections(source_images, config.detection_algorithm_id)
    detectors = {d.detection_algorithm_id for d in detections}
    if config.detection_algorithm_id is None and len(detectors) > 1:
        logger.warning(f"Session {event.pk} has detections from more than one detector: {sorted(detectors, key=str)}.")
        raise SkipSession("its detections come from more than one detector; choose one in the settings")

    position = {image.pk: i for i, image in enumerate(source_images)}
    detections.sort(key=lambda d: (position[d.source_image_id], d.pk))
    detections_by_capture: dict[int, list[Detection]] = collections.defaultdict(list)
    for det in detections:
        detections_by_capture[det.source_image_id].append(det)

    transitions = len(source_images) - 1
    links: list[Link] = []
    without_dimensions = 0
    for i, proposed in enumerate(iter_transition_links(source_images, detections_by_capture, config, logger)):
        if proposed is None:
            without_dimensions += 1
        else:
            links.extend(proposed)
        if progress_cb:
            progress_cb((i + 1) / transitions)
    too_far = sum(
        captures_too_far_apart(source_images[i].timestamp, source_images[i + 1].timestamp, config)
        for i in range(transitions)
    )

    snapshot = {d.pk: (d.next_detection_id, d.occurrence_id) for d in detections}
    all_links = {pk: next_id for pk, (next_id, _) in snapshot.items() if next_id is not None}
    all_links.update({source: target for source, target, _ in links})
    groups = merge_groups(
        [d.pk for d in detections],
        {pk: occurrence_id for pk, (_, occurrence_id) in snapshot.items()},
        all_links,
        {source: cost for source, _, cost in links},
    )
    return SessionPlan(
        event=event,
        source_images=source_images,
        detection_algorithm_id=config.detection_algorithm_id,
        detections={d.pk: d for d in detections},
        snapshot=snapshot,
        links=links,
        groups=groups,
        transitions_too_far_apart=too_far,
        transitions_without_dimensions=without_dimensions,
    )


def plan_is_current(plan: SessionPlan) -> bool:
    """Whether the session still has the captures, links and occurrences the plan was worked out from."""
    if [image.pk for image in processed_captures(plan.event)] != [image.pk for image in plan.source_images]:
        return False
    current = {
        d.pk: (d.next_detection_id, d.occurrence_id)
        for d in session_detections(plan.source_images, plan.detection_algorithm_id)
    }
    return current == plan.snapshot


def lock_occurrences(occurrence_ids: set[int]) -> None:
    """Hold a row lock on each occurrence until the transaction ends, in id order so two writers cannot deadlock.

    An identification saved on a locked occurrence waits until the run commits, so the guard against
    identified sessions sees it, and it is never written on an occurrence the run is about to delete.
    """
    if occurrence_ids:
        list(
            Occurrence.objects.select_for_update()
            .filter(pk__in=sorted(occurrence_ids))
            .order_by("pk")
            .values_list("pk")
        )


def emptied_occurrences(plan: SessionPlan) -> dict[int, int]:
    """Each absorbed occurrence the merge leaves empty, mapped to the occurrence that keeps its detections.

    An absorbed occurrence that also holds detections the plan does not move (in another session, or
    from a detector this run does not compare) keeps them and its records, so it is not merged away.
    The keeper of a group that has none yet is not known before writing, so such groups are left out;
    they have no absorbed occurrences anyway.
    """
    absorbed = {occurrence_id: group.keeper_id for group in plan.groups for occurrence_id in group.absorbed_ids}
    if not absorbed:
        return {}
    in_plan = collections.Counter(
        occurrence_id for _, occurrence_id in plan.snapshot.values() if occurrence_id in absorbed
    )
    in_database = dict(
        Detection.objects.filter(occurrence_id__in=list(absorbed))
        .values("occurrence_id")
        .annotate(n=Count("pk"))
        .values_list("occurrence_id", "n")
    )
    return {
        pk: keeper for pk, keeper in absorbed.items() if keeper is not None and in_database.get(pk, 0) == in_plan[pk]
    }


def preview_counts(plan: SessionPlan, emptied: dict[int, int] | None = None) -> dict[str, int]:
    """The counts a run would report for this session, without changing anything.

    ``emptied`` is ``emptied_occurrences(plan)`` when the caller already has it.
    """
    emptied = emptied_occurrences(plan) if emptied is None else emptied
    before = len(plan.occurrence_ids())
    created = sum(1 for group in plan.groups if group.keeper_id is None)
    return {
        "links_created": len(plan.links),
        "occurrences_before": before,
        "occurrences_after": before + created - len(emptied),
        "occurrences_created": created,
        "occurrences_merged": len(emptied),
        "transitions_too_far_apart": plan.transitions_too_far_apart,
        "transitions_without_dimensions": plan.transitions_without_dimensions,
    }


def _set_detection_column(column: str, values: dict[int, int]) -> None:
    """Set one id column on many detections in a single statement, ``{detection id: value}``.

    ``bulk_update`` would build a CASE with a branch per row, which takes seconds of Python for a busy
    session. Django-cachalot invalidates the table for raw writes too.
    """
    if not values:
        return
    table = connection.ops.quote_name(Detection._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f"UPDATE {table} AS d SET {connection.ops.quote_name(column)} = v.value "
            "FROM unnest(%s::bigint[], %s::bigint[]) AS v(id, value) WHERE d.id = v.id",
            [list(values), list(values.values())],
        )


def _withdraw_duplicate_identifications(occurrence_ids: set[int]) -> list[int]:
    """Leave each user one active identification per occurrence, the newest, as saving an identification does.

    Identifications moved by a merge skip ``Identification.save``, so a user who identified two of the
    merged occurrences would otherwise hold two active identifications on the one that is kept.
    Returns the ids withdrawn.
    """
    seen: set[tuple[int, int]] = set()
    withdraw: list[int] = []
    for pk, occurrence_id, user_id in (
        Identification.objects.filter(occurrence_id__in=occurrence_ids, withdrawn=False, user__isnull=False)
        .order_by("occurrence_id", "user_id", "-created_at", "-pk")
        .values_list("pk", "occurrence_id", "user_id")
    ):
        if (occurrence_id, user_id) in seen:
            withdraw.append(pk)
        else:
            seen.add((occurrence_id, user_id))
    if withdraw:
        Identification.objects.filter(pk__in=withdraw).update(withdrawn=True)
    return withdraw


def record_tracking_results(
    groups: Sequence[MergeGroup],
    keepers: dict[int, Occurrence],
    plan: SessionPlan,
    algorithm: Algorithm,
    job: "Job | None",
    merged: dict[int, list[int]],
    moved_identifications: dict[int, list[tuple[int, int]]],
    withdrawn: dict[int, list[int]],
    determination_before: dict[int, int | None],
) -> int:
    """Write one tracking result per group of two or more detections, or that absorbed an occurrence.

    The figures are computed in memory from the plan's detections plus one query for each detection's
    label: its best classification at the time of the run, chosen as the determination chooses (terminal
    first, then the highest score), so the taxa and agreement describe what the determination was made from.
    Each result also records the occurrence every detection was in before the run, and the
    identifications moved or withdrawn, so a reset can put the earlier grouping back. Returns the
    number of results written.
    """
    recorded = [(g, keepers[g.keeper_id]) for g in groups if len(g.detection_ids) > 1 or merged.get(g.keeper_id)]
    if not recorded:
        return 0
    detection_ids = [pk for group, _ in recorded for pk in group.detection_ids]
    labels = {
        row[0]: Label(*row)
        for row in Classification.objects.filter(detection_id__in=detection_ids)
        .order_by("detection_id", "-terminal", F("score").desc(nulls_last=True), "-created_at")
        .distinct("detection_id")
        .values_list("detection_id", "taxon_id", "taxon__name", "score")
    }

    images = {image.pk: image for image in plan.source_images}
    results = []
    for group, keeper in recorded:
        detections = [plan.detections[pk] for pk in group.detection_ids]
        figures = occurrence_figures(
            boxes=[d.bbox for d in detections],
            sizes=[(images[d.source_image_id].width, images[d.source_image_id].height) for d in detections],
            labels=[labels[d.pk] for d in detections if d.pk in labels],
            determination_id=keeper.determination_id,
            timestamps=[images[d.source_image_id].timestamp for d in detections],
        )
        results.append(
            AlgorithmResult(
                occurrence=keeper,
                algorithm=algorithm,
                job=job,
                kind=TrackingResultData.kind,
                data={
                    **dataclasses.asdict(figures),
                    "link_costs": group.link_costs,
                    "determination_before_id": determination_before.get(keeper.pk),
                    "determination_after_id": keeper.determination_id,
                    "merged_occurrence_ids": merged.get(keeper.pk, []),
                    "detection_ids": group.detection_ids,
                    "previous_occurrence_ids": group.previous_occurrence_ids,
                    "moved_identifications": moved_identifications.get(keeper.pk, []),
                    "withdrawn_identification_ids": withdrawn.get(keeper.pk, []),
                },
            )
        )
    return len(AlgorithmResult.objects.record_many(results))


def write_session_plan(
    plan: SessionPlan,
    logger: logging.Logger,
    record_as: Algorithm | None = None,
    job: "Job | None" = None,
) -> dict[str, int]:
    """Save a plan's links and merges, writing each table in a few bulk statements.

    Call inside the session's transaction, holding the session and occurrence locks, after checking
    ``plan_is_current``. The statements do not grow with the number of detections; the determination
    recompute costs a few queries per changed occurrence. It does no progress writes, since saving the
    job inside the transaction would keep its row locked.
    """
    emptied = emptied_occurrences(plan)
    counters = preview_counts(plan, emptied)

    _set_detection_column("next_detection_id", {source: target for source, target, _ in plan.links})

    # Groups with no occurrence get a new one in the session.
    to_create = [group for group in plan.groups if group.keeper_id is None]
    created = Occurrence.objects.bulk_create(
        [
            Occurrence(event=plan.event, deployment_id=plan.event.deployment_id, project_id=plan.event.project_id)
            for _ in to_create
        ]
    )
    for group, occurrence in zip(to_create, created):
        group.keeper_id = occurrence.pk

    _set_detection_column(
        "occurrence_id",
        {
            pk: group.keeper_id
            for group in plan.groups
            for pk, previous in zip(group.detection_ids, group.previous_occurrence_ids)
            if previous != group.keeper_id
        },
    )

    keeper_ids = {group.keeper_id for group in plan.groups}
    keepers = Occurrence.objects.select_related("determination").in_bulk(list(keeper_ids))
    determination_before = {pk: keeper.determination_id for pk, keeper in keepers.items()}

    merged: dict[int, list[int]] = collections.defaultdict(list)
    for pk, keeper_id in sorted(emptied.items()):
        merged[keeper_id].append(pk)

    # Identifications and results of the emptied occurrences move onto their keepers before the delete,
    # which would otherwise cascade to them.
    moved_identifications: dict[int, list[tuple[int, int]]] = collections.defaultdict(list)
    for pk, occurrence_id in Identification.objects.filter(occurrence_id__in=list(emptied)).values_list(
        "pk", "occurrence_id"
    ):
        moved_identifications[emptied[occurrence_id]].append((pk, occurrence_id))
    for keeper_id, moved in moved_identifications.items():
        Identification.objects.filter(pk__in=[pk for pk, _ in moved]).update(occurrence_id=keeper_id)
    withdrawn: dict[int, list[int]] = collections.defaultdict(list)
    for pk, occurrence_id in Identification.objects.filter(
        pk__in=_withdraw_duplicate_identifications(set(moved_identifications))
    ).values_list("pk", "occurrence_id"):
        withdrawn[occurrence_id].append(pk)

    # Every keeper and emptied occurrence is in the session being tracked, so all share one project.
    with_results = set(
        AlgorithmResult.objects.filter(occurrence_id__in=list(emptied))
        .values_list("occurrence_id", flat=True)
        .distinct()
    )
    for keeper_id, absorbed in merged.items():
        if with_results.intersection(absorbed):
            AlgorithmResult.objects.filter(occurrence_id__in=absorbed).update(occurrence_id=keeper_id)
    if emptied:
        Occurrence.objects.filter(pk__in=list(emptied)).delete()

    # The transaction is about to change these tables, so caching its reads only costs a cache key per query.
    # Writes still invalidate the cache. Entered by hand because the context manager does not restore on error.
    uncached = cachalot_disabled()
    uncached.__enter__()
    try:
        changed = [
            keeper
            for keeper in keepers.values()
            if update_occurrence_determination(keeper, current_determination=keeper.determination, save=False)
        ]
    finally:
        uncached.__exit__(None, None, None)
    Occurrence.objects.bulk_update(changed, ["determination", "determination_score"], batch_size=WRITE_BATCH_SIZE)

    counters["identifications_moved"] = sum(len(moved) for moved in moved_identifications.values())
    counters["identifications_withdrawn"] = sum(len(ids) for ids in withdrawn.values())
    counters["results_recorded"] = (
        record_tracking_results(
            plan.groups, keepers, plan, record_as, job, merged, moved_identifications, withdrawn, determination_before
        )
        if record_as is not None
        else 0
    )
    logger.info(
        f"Session {plan.event.pk}: {counters['links_created']} links, created {counters['occurrences_created']} "
        f"occurrences and merged {counters['occurrences_merged']} (occurrences before: "
        f"{counters['occurrences_before']}, after: {counters['occurrences_after']}). Moved "
        f"{counters['identifications_moved']} identification(s), recorded {counters['results_recorded']} result(s)."
    )
    return counters


def nothing_tracked_summary(skip_reasons: collections.Counter[str]) -> str:
    """The line a job shows when every session in scope was skipped, with the count per reason."""
    total = sum(skip_reasons.values())
    reasons = "; ".join(f"{count} because {reason}" for reason, count in skip_reasons.most_common())
    return f"Nothing was tracked: {total} session(s) skipped ({reasons})."


class TrackingTask(BasePostProcessingTask):
    """Link detections across consecutive processed captures and merge the occurrences each chain joins.

    Sets each detection's ``next_detection`` link from bounding-box overlap, size and distance,
    then merges every group of linked detections into a single occurrence per session.
    """

    key = "tracking"
    name = "Occurrence tracking"
    config_schema = TrackingConfig
    result_models = (TrackingResultData,)

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

    def _check_guards(self, event: Event) -> None:
        """Raise ``SkipSession`` when a guard in the settings keeps this session from being tracked."""
        if self.config.require_fresh_event and session_has_links(event):
            raise SkipSession("it was already tracked")
        if self.config.skip_if_human_identifications and session_has_identifications(event):
            raise SkipSession("it has human identifications")

    def _track_session(self, event: Event, progress_cb: typing.Callable[[float], None] | None = None):
        """Track one session in two phases, returning ``(counters, None)`` or ``(None, skip reason)``.

        Matching reads only and runs outside any transaction, so the job can keep saving progress
        while it works. Writing is one short transaction that locks the session and its occurrences,
        repeats the guards, and refuses to write when the session changed since it was matched. In
        preview mode the plan's counts are returned and nothing is written.
        """
        try:
            self._check_guards(event)
            plan = plan_session_links(event, self.logger, self.config, progress_cb)
            if self.config.preview_only:
                return preview_counts(plan), None
            with transaction.atomic():
                lock_sessions([event.pk])
                lock_occurrences(plan.occurrence_ids())
                self._check_guards(event)
                if not plan_is_current(plan):
                    raise SkipSession("it changed while it was being tracked")
                return write_session_plan(plan, self.logger, record_as=self.algorithm, job=self.job), None
        except SkipSession as skip:
            self.logger.info(f"Skipping session {event.pk}: {skip}.")
            return None, str(skip)

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
        session failed, so the job is marked failed. In preview mode the same counts are reported and
        nothing is written.
        """
        preview = self.config.preview_only
        self.logger.info(f"Tracking {'preview ' if preview else ''}starting with config: {self.config.dict()}")

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
                totals.update(counters)
            elif reason is not None:
                totals["skipped"] += 1
                skip_reasons[reason] += 1
            # Saved between sessions, after the transaction has committed, so the bar moves per session.
            self.update_progress(idx / total)

        if not preview:
            # Merging occurrences changes the session and station counts, which no save refreshes.
            update_calculated_fields_for_sessions_and_stations(tracked_event_ids)

        would = "that would be " if preview else ""
        metrics: dict[str, typing.Any] = {
            "Sessions tracked" if not preview else "Sessions previewed": totals["tracked"],
            "Sessions skipped": totals["skipped"],
            "Sessions failed": len(failed_event_ids),
            f"Detection links {would}created": totals["links_created"],
            f"Occurrences {would}merged away": totals["occurrences_merged"],
            "Occurrences before": totals["occurrences_before"],
            "Occurrences after" if not preview else "Occurrences after the run": totals["occurrences_after"],
        }
        if not preview:
            metrics["Occurrences recorded"] = totals["results_recorded"]
            metrics["Identifications moved"] = totals["identifications_moved"]
        if self.config.max_capture_interval_seconds is not None:
            metrics["Capture pairs too far apart to compare"] = totals["transitions_too_far_apart"]
        # The job still succeeds when every session is skipped, so this line is written on every run:
        # a retry keeps text params, and a stale line would contradict the counts.
        if failed_event_ids:
            metrics["Result"] = (
                f"Tracking failed for {len(failed_event_ids)} of {total} session(s) "
                f"(ids {failed_event_ids}); {totals['tracked']} were tracked."
            )
        elif totals["tracked"] and preview:
            metrics["Result"] = (
                f"Preview only, nothing was changed. Tracking {totals['tracked']} session(s) would create "
                f"{totals['links_created']} links and merge away {totals['occurrences_merged']} occurrences "
                f"({totals['occurrences_before']} before, {totals['occurrences_after']} after)."
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
