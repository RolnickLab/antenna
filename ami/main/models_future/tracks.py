"""Operations for correcting a track after tracking has grouped it.

A track is a run of detections that tracking decided are the same insect, all
attached to one occurrence and linked in time order through
``Detection.next_detection``.

Tracking errs toward leaving one animal as two occurrences rather than merging
two animals into one, because a wrong merge destroys a record that no later
step recovers. These operations are the repair for the merges it still gets
wrong: cut a track in two, or pull a single detection out of it.

All operations work on the occurrence's detections in timestamp order, which is
what the occurrence view shows. That means they behave sensibly on occurrences
that were never tracked and so carry no links at all.

Five invariants hold after every operation here:

- Every occurrence the edit touched is linked frame to frame in capture order within
  each session (``relink_occurrence_chains``), so a confirmed track exports as one
  unbroken chain.
- A chain link never crosses an occurrence boundary within one session. Otherwise
  a later tracking pass would walk the chain, decide both occurrences are one, and
  undo the edit. Tracking stops at session boundaries, so the link a regroup keeps
  between the pieces of a track it split (``split_at_session_boundaries``) is safe.
- An edit that changes which detections an occurrence holds clears its grouping
  verification. A person confirmed the set they were shown, not a later one.
- The stored track statistics of every surviving occurrence the edit touched are
  recomputed, so the list sorts on current numbers. This costs three queries per
  edit however many occurrences it touched (see ``track_stats.refresh_track_stats``).
- The cached counts of the sessions and stations the edit touched are refreshed once,
  since an edit adds or removes occurrences.
"""

from __future__ import annotations

import datetime
from collections import Counter
from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from ami.main.models import (
    Detection,
    Identification,
    Occurrence,
    SourceImage,
    User,
    update_calculated_fields_for_sessions_and_stations,
    update_occurrence_determination,
)
from ami.main.models_future.track_stats import refresh_track_stats


class TrackEditError(ValueError):
    """A track edit that cannot be applied to this occurrence and detection."""


def _ordered_detections(occurrence: Occurrence) -> list[Detection]:
    return list(occurrence.detections.select_related("source_image").order_by("timestamp", "pk"))


def _move_to_new_occurrence(occurrence: Occurrence, detections: list[Detection]) -> Occurrence:
    """Attach ``detections``, in time order, to a new occurrence beside ``occurrence``.

    The new occurrence takes the session of its first detection's capture, which after a
    regroup need not be the session of ``occurrence``.
    """
    new_occurrence = Occurrence.objects.create(
        event_id=detections[0].source_image.event_id,
        deployment=occurrence.deployment,
        project=occurrence.project,
    )
    Detection.objects.filter(pk__in=[d.pk for d in detections]).update(occurrence=new_occurrence)
    return new_occurrence


@transaction.atomic
def split_track(occurrence: Occurrence, detection: Detection) -> Occurrence:
    """Split ``occurrence`` so ``detection`` and everything after it become a new occurrence.

    Use when a track ran two animals together: the frame where the second one
    takes over is the split point. Returns the new occurrence holding the tail.

    "After" means later in time. Note that the occurrence detail endpoint
    serves detections newest-first (prefetch_detections_for_detail), so an
    interface that splits at the frame the operator clicked must map the
    displayed position back to timestamp order, or it will keep the wrong half.
    """
    ordered = _ordered_detections(occurrence)
    index = next((i for i, d in enumerate(ordered) if d.pk == detection.pk), None)
    if index is None:
        raise TrackEditError(f"Detection {detection.pk} does not belong to occurrence {occurrence.pk}.")
    if index == 0:
        raise TrackEditError(
            f"Detection {detection.pk} is the first in occurrence {occurrence.pk}; "
            "there is nothing before it to split from."
        )

    new_occurrence = _move_to_new_occurrence(occurrence, ordered[index:])
    relink_occurrence_chains([occurrence, new_occurrence])

    _clear_verification(occurrence, new_occurrence)
    occurrence.save()
    new_occurrence.save()
    refresh_track_stats(occurrence, new_occurrence)
    update_calculated_fields_for_sessions_and_stations([occurrence.event_id, new_occurrence.event_id])
    return new_occurrence


@transaction.atomic
def detach_detection(occurrence: Occurrence, detection: Detection) -> Occurrence:
    """Pull one detection out of ``occurrence`` into an occurrence of its own.

    Use when a single frame was matched into the wrong track. The rest of the
    track is stitched back together across the gap, so removing a detection from
    the middle does not also split what remains. Returns the new occurrence.
    """
    ordered = _ordered_detections(occurrence)
    if len(ordered) < 2:
        raise TrackEditError(
            f"Occurrence {occurrence.pk} has a single detection; removing it would leave the occurrence empty."
        )
    index = next((i for i, d in enumerate(ordered) if d.pk == detection.pk), None)
    if index is None:
        raise TrackEditError(f"Detection {detection.pk} does not belong to occurrence {occurrence.pk}.")

    new_occurrence = _move_to_new_occurrence(occurrence, [ordered[index]])
    relink_occurrence_chains([occurrence, new_occurrence])

    _clear_verification(occurrence, new_occurrence)
    occurrence.save()
    new_occurrence.save()
    refresh_track_stats(occurrence, new_occurrence)
    update_calculated_fields_for_sessions_and_stations([occurrence.event_id, new_occurrence.event_id])
    return new_occurrence


@transaction.atomic
def split_at_session_boundaries(occurrence: Occurrence) -> list[Occurrence]:
    """Split an occurrence whose detections fall in several sessions into one per session.

    Regrouping captures into sessions can draw a boundary through a track, and an
    occurrence is expected to belong to one session. The piece in the earliest session
    keeps this occurrence and its identifications; each later piece is a new occurrence
    holding copies of them. Unlike a manual split, every piece keeps the grouping
    confirmation and the chain link to the next piece, since each piece is still the
    whole track within its session and the link records that they are one animal.
    Returns the new occurrences in time order, or an empty list when nothing was split.
    """
    detections = occurrence.detections.select_related("source_image").order_by(
        "source_image__timestamp", "source_image_id", "pk"
    )
    by_session: dict[int, list[Detection]] = {}
    for detection in detections:
        # A capture with no session stays with the earliest piece.
        if detection.source_image.event_id is not None:
            by_session.setdefault(detection.source_image.event_id, []).append(detection)
    if len(by_session) < 2:
        return []

    earliest_event_id, *later_event_ids = by_session
    pieces = [_move_to_new_occurrence(occurrence, by_session[event_id]) for event_id in later_event_ids]
    piece_pks = [piece.pk for piece in pieces]

    if occurrence.event_id != earliest_event_id:
        occurrence.event_id = earliest_event_id
        Occurrence.objects.filter(pk=occurrence.pk).update(event_id=earliest_event_id)
    if occurrence.grouping_verified_at is not None:
        for piece in pieces:
            piece.grouping_verified_at = occurrence.grouping_verified_at
            piece.grouping_verified_by_id = occurrence.grouping_verified_by_id
        Occurrence.objects.filter(pk__in=piece_pks).update(
            grouping_verified_at=occurrence.grouping_verified_at,
            grouping_verified_by_id=occurrence.grouping_verified_by_id,
        )

    _copy_identifications(occurrence, pieces)
    for piece in [occurrence, *pieces]:
        update_occurrence_determination(piece, save=True)
    refresh_track_stats(occurrence, *pieces)
    return pieces


def _copy_identifications(source: Occurrence, targets: list[Occurrence]) -> None:
    """Give each target a copy of every identification on ``source``, dated as the original.

    Written with ``bulk_create`` to skip ``Identification.save()``, which would withdraw
    the user's other identifications on the target. The caller recomputes determinations.
    """
    originals = list(source.identifications.all())
    if not originals or not targets:
        return
    note = f"Copied from occurrence {source.pk} when regrouping split it at a session boundary."
    pairs = [(original, target) for target in targets for original in originals]
    copies = Identification.objects.bulk_create(
        [
            Identification(
                occurrence=target,
                user_id=original.user_id,
                taxon_id=original.taxon_id,
                withdrawn=original.withdrawn,
                comment=f"{original.comment}\n{note}" if original.comment else note,
            )
            for original, target in pairs
        ]
    )
    # created_at is auto_now_add, so the original date can only be written after the insert.
    for copy, (original, _) in zip(copies, pairs):
        copy.created_at = original.created_at
    Identification.objects.bulk_update(copies, ["created_at"])


def _in_different_sessions(a: int | None, b: int | None) -> bool:
    return a is not None and b is not None and a != b


def relink_occurrence_chains(occurrences: Iterable[Occurrence]) -> None:
    """Rewrite the chain links of ``occurrences`` to match the detections they now hold.

    The detections of each occurrence are linked one after another in capture-time
    order, so after a manual edit the chain agrees with the membership a reviewer
    confirmed and the tracks export can follow it frame by frame. Within an occurrence,
    two consecutive detections from different sessions are not linked, and only the
    first box on a capture joins the chain. Links from these detections to detections
    outside them, and into them from outside, are cut, since a later tracking pass
    would walk such a link and fold the occurrences back together.

    A link into another session that some other occurrence holds records one animal
    across a session boundary (see ``split_at_session_boundaries``) and tracking never
    walks it, so it is kept, moved to the last frame of that session's run or to the
    first frame of the run it points into. Costs two reads and at most two writes
    however many occurrences and detections are involved.
    """
    occurrence_pks = {o.pk for o in occurrences if o.pk is not None}
    if not occurrence_pks:
        return
    members = list(
        Detection.objects.valid()
        .filter(occurrence_id__in=occurrence_pks)
        .order_by()
        .values(
            "pk",
            "occurrence_id",
            "source_image_id",
            "source_image__timestamp",
            "source_image__event_id",
            "next_detection_id",
            "next_detection__occurrence_id",
            "next_detection__source_image__event_id",
        )
    )
    member_pks = [m["pk"] for m in members]
    if not member_pks:
        return
    inbound = list(
        Detection.objects.filter(next_detection_id__in=member_pks)
        .exclude(pk__in=member_pks)
        .order_by()
        .values("pk", "occurrence_id", "source_image__event_id", "next_detection_id")
    )

    by_pk = {m["pk"]: m for m in members}
    current: dict[int, int | None] = {m["pk"]: m["next_detection_id"] for m in members}
    current.update({row["pk"]: row["next_detection_id"] for row in inbound})
    desired: dict[int, int | None] = {pk: None for pk in current}
    # Each chained member maps to the first and last frame of its session's run.
    run_head: dict[int, int] = {}
    run_tail: dict[int, int] = {}

    by_occurrence: dict[int, list[dict]] = {}
    for member in members:
        by_occurrence.setdefault(member["occurrence_id"], []).append(member)
    for rows in by_occurrence.values():
        rows.sort(
            key=lambda m: (
                m["source_image__timestamp"] is None,
                m["source_image__timestamp"] or datetime.datetime.min,
                m["source_image_id"],
                m["pk"],
            )
        )
        chain: list[dict] = []
        for row in rows:
            if chain and chain[-1]["source_image_id"] == row["source_image_id"]:
                continue  # A second box on a capture is a second animal: leave it unlinked.
            chain.append(row)
        runs: list[list[dict]] = []
        for row in chain:
            if runs and not _in_different_sessions(
                runs[-1][-1]["source_image__event_id"], row["source_image__event_id"]
            ):
                runs[-1].append(row)
            else:
                runs.append([row])
        for run in runs:
            for earlier, later in zip(run, run[1:]):
                desired[earlier["pk"]] = later["pk"]
            for row in run:
                run_head[row["pk"]], run_tail[row["pk"]] = run[0]["pk"], run[-1]["pk"]

    # Carry over the links into another session that some other occurrence holds.
    carried: list[tuple[int, int, int | None, int | None, int | None, int | None]] = [
        (
            m["pk"],
            m["next_detection_id"],
            m["occurrence_id"],
            m["next_detection__occurrence_id"],
            m["source_image__event_id"],
            m["next_detection__source_image__event_id"],
        )
        for m in members
        if m["next_detection_id"] is not None
    ]
    carried += [
        (
            row["pk"],
            row["next_detection_id"],
            row["occurrence_id"],
            by_pk[row["next_detection_id"]]["occurrence_id"],
            row["source_image__event_id"],
            by_pk[row["next_detection_id"]]["source_image__event_id"],
        )
        for row in inbound
    ]
    taken = {target for target in desired.values() if target is not None}
    for source, target, source_occurrence, target_occurrence, source_event, target_event in sorted(carried):
        if source_occurrence == target_occurrence or not _in_different_sessions(source_event, target_event):
            continue
        if (source in by_pk and source not in run_tail) or (target in by_pk and target not in run_head):
            continue
        source, target = run_tail.get(source, source), run_head.get(target, target)
        if desired.get(source) is None and target not in taken:
            desired[source] = target
            taken.add(target)

    changed = [pk for pk, target in desired.items() if current[pk] != target]
    if not changed:
        return
    # next_detection is unique and Postgres checks it row by row, so clear every
    # changed link before writing the new ones.
    Detection.objects.filter(pk__in=changed).update(next_detection=None)
    relinked = [Detection(pk=pk, next_detection_id=desired[pk]) for pk in changed if desired[pk] is not None]
    if relinked:
        Detection.objects.bulk_update(relinked, ["next_detection"])


def _clear_verification(*occurrences: Occurrence) -> None:
    """Drop grouping verification from occurrences whose detection set just changed.

    Clears the loaded instances as well as the rows: a caller that saves the instance
    afterwards would otherwise write the stale confirmation straight back.
    """
    pks = [o.pk for o in occurrences if o.pk is not None]
    for occurrence in occurrences:
        occurrence.grouping_verified_at = None
        occurrence.grouping_verified_by = None
    if pks:
        Occurrence.objects.filter(pk__in=pks).update(grouping_verified_at=None, grouping_verified_by=None)


def _absorb(target: Occurrence, sources: list[Occurrence]) -> None:
    """Move every detection and identification off ``sources`` and delete them.

    Identifications move first. ``Identification.occurrence`` cascades on delete, so
    a source removed before its identifications were reassigned would take a
    person's work with it.
    """
    source_pks = [o.pk for o in sources]
    if not source_pks:
        return
    Identification.objects.filter(occurrence_id__in=source_pks).update(occurrence=target)
    Detection.objects.filter(occurrence_id__in=source_pks).update(occurrence=target)
    Occurrence.objects.filter(pk__in=source_pks).delete()


def _refuse_two_boxes_on_one_capture(target: Occurrence, incoming_capture_ids: Iterable[int]) -> None:
    """Refuse an edit that would put two boxes from one capture into ``target``.

    One animal appears at most once per capture, so a second box on a capture is a
    second individual. Only captures the edit brings in are checked, so a track that
    already holds such a pair can still be edited.
    """
    counts = Counter(incoming_capture_ids)
    if not counts:
        return
    covered = set(
        Detection.objects.valid()
        .filter(occurrence_id=target.pk, source_image_id__in=list(counts))
        .values_list("source_image_id", flat=True)
    )
    clashes = covered | {capture_id for capture_id, n in counts.items() if n > 1}
    if clashes:
        # Reviewers read this in the merge and extend dialogs, so name capture times, not ids.
        timestamps = (
            SourceImage.objects.filter(pk__in=clashes).order_by("timestamp", "pk").values_list("timestamp", flat=True)
        )
        times = ", ".join(_time_of_day(timestamp) for timestamp in timestamps)
        captures = "the capture" if len(clashes) == 1 else "the captures"
        raise TrackEditError(
            f"This would put two detections from {captures} at {times} into one track. "
            "One animal appears once per capture, so these are different individuals."
        )


def _time_of_day(timestamp: datetime.datetime | None) -> str:
    """A capture time as a reviewer reads it on the session page, e.g. 10:48:23 PM."""
    if timestamp is None:
        return "an unknown time"
    return timestamp.strftime("%I:%M:%S %p").lstrip("0")


@transaction.atomic
def merge_occurrences(target: Occurrence, sources: Iterable[Occurrence]) -> Occurrence:
    """Fold ``sources`` into ``target``: one animal that tracking recorded as several.

    Every detection and identification moves to ``target`` and the emptied sources
    are deleted. Sources must belong to the same session, since an occurrence
    cannot span two nights.
    """
    sources = [o for o in sources if o.pk != target.pk]
    if not sources:
        raise TrackEditError("Nothing to merge: no occurrence other than the target was given.")

    cross_session = sorted(o.pk for o in sources if o.event_id != target.event_id)
    if cross_session:
        raise TrackEditError(
            f"Occurrence(s) {cross_session} belong to a different session than {target.pk}. "
            "An occurrence cannot span sessions."
        )
    _refuse_two_boxes_on_one_capture(
        target,
        Detection.objects.valid()
        .filter(occurrence_id__in=[o.pk for o in sources])
        .values_list("source_image_id", flat=True),
    )

    _absorb(target, sources)
    relink_occurrence_chains([target])
    _clear_verification(target)
    target.save()
    refresh_track_stats(target)
    update_calculated_fields_for_sessions_and_stations([target.event_id])
    return target


def _fill_timestamps_from_captures(detections: Iterable[Detection]) -> None:
    """Give every detection the timestamp of its capture, as ``Detection.save`` does.

    A detection that was never grouped can reach a track without one, and an undated
    detection sorts outside its own track and is skipped by the track statistics.
    Written in a single query so the cost does not follow how many moved.
    """
    undated = [d for d in detections if d.timestamp is None]
    if not undated:
        return
    for detection in undated:
        detection.timestamp = detection.source_image.timestamp
    Detection.objects.bulk_update(undated, ["timestamp"])


@transaction.atomic
def add_detections(target: Occurrence, detections: Iterable[Detection]) -> Occurrence:
    """Move individual detections into ``target``.

    Use when a frame belongs to this animal but landed on its own, on the wrong
    occurrence, or on no occurrence at all, which is how a detector-only project
    leaves most of its boxes. A detection with no occurrence simply moves in; there
    is no donor to absorb. Any occurrence left with no detections is absorbed rather
    than deleted outright, so identifications on it survive.
    """
    detections = [d for d in detections if d.occurrence_id != target.pk]
    if not detections:
        raise TrackEditError("Nothing to add: every detection given is already in this occurrence.")

    donor_pks = {d.occurrence_id for d in detections if d.occurrence_id}
    cross_session = sorted(
        d.pk for d in detections if d.source_image.event_id and d.source_image.event_id != target.event_id
    )
    if cross_session:
        raise TrackEditError(
            f"Detection(s) {cross_session} were captured in a different session than occurrence "
            f"{target.pk}. An occurrence cannot span sessions."
        )
    _refuse_two_boxes_on_one_capture(target, [d.source_image_id for d in detections])

    donors = list(Occurrence.objects.filter(pk__in=donor_pks))
    Detection.objects.filter(pk__in=[d.pk for d in detections]).update(occurrence=target)
    _fill_timestamps_from_captures(detections)

    emptied = [o for o in donors if not o.detections.exists()]
    _absorb(target, emptied)

    remaining = [o for o in donors if o.pk not in {e.pk for e in emptied}]
    relink_occurrence_chains([target, *remaining])
    for donor in remaining:
        donor.save()

    _clear_verification(target, *remaining)
    target.save()
    refresh_track_stats(target, *remaining)
    update_calculated_fields_for_sessions_and_stations([target.event_id, *(donor.event_id for donor in donors)])
    return target


def verify_grouping(occurrence: Occurrence, user: User) -> Occurrence:
    """Record that a person confirmed this occurrence holds the right detections.

    This is the label the tracking methods are scored against, so it is deliberately
    an explicit act — no operation in this module sets it as a side effect.
    """
    occurrence.grouping_verified_at = timezone.now()
    occurrence.grouping_verified_by = user
    occurrence.save(update_fields=["grouping_verified_at", "grouping_verified_by"])
    return occurrence


def unverify_grouping(occurrence: Occurrence) -> Occurrence:
    """Withdraw a previous confirmation, leaving the detections untouched."""
    occurrence.grouping_verified_at = None
    occurrence.grouping_verified_by = None
    occurrence.save(update_fields=["grouping_verified_at", "grouping_verified_by"])
    return occurrence
