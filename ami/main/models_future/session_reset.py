"""Undo tracking for a session: put every detection back in an occurrence of its own.

Tracking only runs on a session whose occurrences each hold a single detection (see
``tracking_task.event_is_fresh``). Resetting returns a tracked session to that state,
so the same night can be tracked again with other settings, or looked at as it was
before tracking. It is a staff tool: it throws away every grouping in the session,
including groupings a person confirmed.

After a reset, for every detection of the session that shared an occurrence:

- The earliest detection (in capture order) keeps the occurrence; each other
  detection in the session moves to a new occurrence of its own. An occurrence that
  also holds detections of another session stays with those detections, untouched
  there, and every detection of this session leaves it.
- Every occurrence the split touched takes its determination from its own
  detections' best prediction, the rule ``Occurrence.best_prediction`` applies, or
  none if they have no scored prediction. An
  occurrence with a human identification keeps the determination it has.
- Chain links between two detections of the session are cleared. A link that crosses
  into another session records one animal across a regroup boundary, which tracking
  never follows, so it is kept.
- Grouping verification is cleared on every occurrence of the session.
- Classifications the tracking task recorded on the session's detections are deleted.
  Each is a copy of a prediction on the same detection, made when a merge changed a
  determination, so it describes a merge that no longer exists.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from django.db import transaction
from django.db.models import Count, Prefetch, Q

from ami.main.models import (
    Classification,
    Detection,
    Event,
    Identification,
    Occurrence,
    update_calculated_fields_for_sessions_and_stations,
)
from ami.main.models_future.occurrence import best_prediction_from_prefetch
from ami.main.models_future.track_stats import refresh_track_stats_for_ids
from ami.main.models_future.tracks import _capture_order_key

# Occurrences whose determination is recomputed per round trip. Each batch reads the
# occurrences, their detections and those detections' classifications: three queries.
DETERMINATION_BATCH_SIZE = 2000

# The Algorithm key the tracking task records its determination changes under.
TRACKING_ALGORITHM_KEY = "tracking"


class SessionResetRefused(ValueError):
    """The session holds work a reset would discard, and the caller did not force it."""


@dataclasses.dataclass
class SessionTrackingCounts:
    """How grouped a session is, read through its detections' captures."""

    occurrences: int
    multi_detection_occurrences: int
    determinations: int
    links: int
    grouping_verified: int


@dataclasses.dataclass
class SessionResetResult:
    event_id: int
    dry_run: bool
    identifications: int
    occurrences_split: int
    occurrences_created: int
    links_cleared: int
    verifications_cleared: int
    tracking_classifications_deleted: int
    determinations_updated: int
    before: SessionTrackingCounts
    after: SessionTrackingCounts | None


def _session_detections(event: Event):
    return Detection.objects.filter(source_image__event=event)


def _session_occurrence_ids(event: Event):
    """Occurrences reached through the session's captures, as ``event_is_fresh`` finds them."""
    return _session_detections(event).filter(occurrence__isnull=False).order_by().values("occurrence_id")


def session_tracking_counts(event: Event) -> SessionTrackingCounts:
    """Occurrences, multi-frame occurrences, distinct determinations, links and confirmations. Three queries."""
    occurrences = Occurrence.objects.filter(pk__in=_session_occurrence_ids(event))
    totals = occurrences.aggregate(
        occurrences=Count("pk"),
        determinations=Count("determination", distinct=True),
        grouping_verified=Count("pk", filter=Q(grouping_verified_at__isnull=False)),
    )
    multi = occurrences.annotate(_n=Count("detections")).filter(_n__gt=1).count()
    links = _session_detections(event).filter(next_detection__source_image__event=event).count()
    return SessionTrackingCounts(
        occurrences=totals["occurrences"],
        multi_detection_occurrences=multi,
        determinations=totals["determinations"],
        links=links,
        grouping_verified=totals["grouping_verified"],
    )


def _plan_split(event: Event) -> tuple[list[int], list[int], dict[int, int]]:
    """The multi-detection occurrences of the session, the detections that leave them, and
    the occurrences whose session changes.

    An occurrence that lies wholly in this session keeps its first detection in capture
    order, and its other detections leave. An occurrence that also holds detections of
    another session stays whole there: every detection of this session leaves it, and if
    it was filed under this session it moves to the session of its first remaining
    detection.
    """
    multi = dict(
        Occurrence.objects.filter(pk__in=_session_occurrence_ids(event))
        .annotate(_n=Count("detections"))
        .filter(_n__gt=1)
        .values_list("pk", "event_id")
    )
    if not multi:
        return [], [], {}
    rows = list(
        Detection.objects.filter(occurrence_id__in=multi)
        .order_by()
        .values("pk", "occurrence_id", "source_image_id", "source_image__timestamp", "source_image__event_id")
    )
    by_occurrence: dict[int, list[dict]] = {}
    for row in rows:
        by_occurrence.setdefault(row["occurrence_id"], []).append(row)
    movers: list[int] = []
    new_sessions: dict[int, int] = {}
    for occurrence_id, members in by_occurrence.items():
        members.sort(key=_capture_order_key)
        outside = [row for row in members if row["source_image__event_id"] != event.pk]
        if outside:
            movers.extend(row["pk"] for row in members if row["source_image__event_id"] == event.pk)
            if multi[occurrence_id] == event.pk:
                new_sessions[occurrence_id] = outside[0]["source_image__event_id"]
        else:
            movers.extend(row["pk"] for row in members[1:])
    return list(multi), movers, new_sessions


def _refresh_determinations(occurrence_ids: Iterable[int]) -> int:
    """Set each occurrence's determination to its best prediction, in batches; returns how many changed.

    The batched form of ``update_occurrence_determination`` for occurrences with no
    identifications, using the same choice as ``Occurrence.best_prediction``. Unlike it,
    an occurrence with no scored prediction gets no determination.
    """
    ids = list(occurrence_ids)
    classifications = Classification.objects.select_related(None).only(
        "pk", "detection_id", "algorithm_id", "taxon_id", "score", "terminal"
    )
    detections = (
        Detection.objects.select_related(None)
        .only("pk", "occurrence_id")
        .prefetch_related(Prefetch("classifications", queryset=classifications))
    )
    changed: list[Occurrence] = []
    for start in range(0, len(ids), DETERMINATION_BATCH_SIZE):
        batch = (
            Occurrence.objects.select_related(None)
            .filter(pk__in=ids[start : start + DETERMINATION_BATCH_SIZE])
            .only("pk", "determination_id", "determination_score")
        )
        for occurrence in batch.prefetch_related(Prefetch("detections", queryset=detections)):
            best = best_prediction_from_prefetch(occurrence)
            # With no scored prediction left, a determination inherited from the merged
            # track would describe detections that have moved away, so it is cleared.
            wanted = (best.taxon_id, best.score) if best is not None and best.taxon_id else (None, None)
            if (occurrence.determination_id, occurrence.determination_score) != wanted:
                occurrence.determination_id, occurrence.determination_score = wanted
                changed.append(occurrence)
    Occurrence.objects.bulk_update(changed, ["determination", "determination_score"], batch_size=1000)
    return len(changed)


def reset_session_tracking(event: Event, *, force: bool = False, dry_run: bool = False) -> SessionResetResult:
    """Return ``event`` to one occurrence per detection, with no links and no confirmations.

    Raises ``SessionResetRefused`` when the session's occurrences carry human
    identifications, unless ``force`` is set; forced, each identification stays on the
    occurrence that keeps the first detection. With ``dry_run`` the counts are those a
    reset would produce and nothing is written. The query count depends on the number of
    occurrences only through the determination batches, not per row.
    """
    before = session_tracking_counts(event)
    occurrence_ids = _session_occurrence_ids(event)
    identified = set(
        Identification.objects.filter(occurrence_id__in=occurrence_ids).values_list("occurrence_id", flat=True)
    )
    identification_count = Identification.objects.filter(occurrence_id__in=identified).count() if identified else 0
    if identification_count and not force:
        raise SessionResetRefused(
            f"Session {event.pk} has {identification_count} identification(s) on {len(identified)} occurrence(s). "
            "Resetting would split occurrences a person identified; pass force to reset anyway."
        )

    multi_ids, movers, new_sessions = _plan_split(event)
    links = _session_detections(event).filter(next_detection__source_image__event=event)
    tracking_classifications = Classification.objects.filter(
        detection__source_image__event=event, algorithm__key=TRACKING_ALGORITHM_KEY
    )
    verified = Occurrence.objects.filter(pk__in=occurrence_ids, grouping_verified_at__isnull=False)

    if dry_run:
        return SessionResetResult(
            event_id=event.pk,
            dry_run=True,
            identifications=identification_count,
            occurrences_split=len(multi_ids),
            occurrences_created=len(movers),
            links_cleared=before.links,
            verifications_cleared=before.grouping_verified,
            tracking_classifications_deleted=tracking_classifications.count(),
            determinations_updated=0,
            before=before,
            after=None,
        )

    with transaction.atomic():
        links_cleared = links.update(next_detection=None)
        verifications_cleared = verified.update(grouping_verified_at=None, grouping_verified_by=None)
        _, deleted_by_model = tracking_classifications.delete()
        tracking_deleted = deleted_by_model.get(Classification._meta.label, 0)

        new_occurrences = Occurrence.objects.bulk_create(
            [Occurrence(event=event, deployment_id=event.deployment_id, project_id=event.project_id) for _ in movers],
            batch_size=1000,
        )
        Detection.objects.bulk_update(
            [
                Detection(pk=detection_id, occurrence_id=occurrence.pk)
                for detection_id, occurrence in zip(movers, new_occurrences)
            ],
            ["occurrence"],
            batch_size=1000,
        )

        Occurrence.objects.bulk_update(
            [Occurrence(pk=pk, event_id=session_id) for pk, session_id in new_sessions.items()], ["event"]
        )

        touched = [*multi_ids, *(o.pk for o in new_occurrences)]
        determinations_updated = _refresh_determinations(pk for pk in touched if pk not in identified)
        refresh_track_stats_for_ids(touched)

    update_calculated_fields_for_sessions_and_stations(
        [event.pk, *set(new_sessions.values())], stations_async=False
    )
    return SessionResetResult(
        event_id=event.pk,
        dry_run=False,
        identifications=identification_count,
        occurrences_split=len(multi_ids),
        occurrences_created=len(new_occurrences),
        links_cleared=links_cleared,
        verifications_cleared=verifications_cleared,
        tracking_classifications_deleted=tracking_deleted,
        determinations_updated=determinations_updated,
        before=before,
        after=session_tracking_counts(event),
    )
