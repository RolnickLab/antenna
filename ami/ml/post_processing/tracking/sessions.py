"""Session locking and splitting of occurrences at session boundaries, for tracking and regrouping.

Tracking links the detections of one insect through ``Detection.next_detection`` and attaches
the chain to a single occurrence. Chains never cross a session boundary, but regrouping
captures into sessions can draw a new boundary through an existing occurrence. The functions
here lock sessions against concurrent writers and split such an occurrence into one per session.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.db.models import F

from ami.main.models import Detection, Event, Identification, Occurrence, SourceImage, update_occurrence_determination

# Order of detections within an occurrence: capture time, then capture, then detection.
CAPTURE_ORDER = (F("source_image__timestamp").asc(nulls_last=True), "source_image_id", "pk")


def lock_sessions(event_ids: Iterable[int | None]) -> None:
    """Hold a row lock on each session until the surrounding transaction ends.

    Tracking runs and regroup splits both call this before reading what they change, so one
    waits for the other. Locking in id order keeps two writers from deadlocking.
    """
    pks = sorted({pk for pk in event_ids if pk is not None})
    if not pks:
        return
    list(Event.objects.select_for_update().filter(pk__in=pks).order_by("pk").values_list("pk", flat=True))


def _move_to_new_occurrence(occurrence: Occurrence, detections: list[Detection]) -> Occurrence:
    """Attach ``detections`` to a new occurrence beside ``occurrence``.

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
def split_at_session_boundaries(occurrence: Occurrence) -> list[Occurrence]:
    """Split an occurrence whose detections fall in several sessions into one per session.

    The piece in the earliest session keeps this occurrence and its identifications; each
    later piece is a new occurrence holding copies of them. The link between the last
    detection of one piece and the first of the next is kept, since tracking stops at session
    boundaries and so never walks across it. Returns the new occurrences in time order, or an
    empty list when nothing was split.
    """
    sessions = SourceImage.objects.filter(detections__occurrence=occurrence).values_list("event_id", flat=True)
    lock_sessions([occurrence.event_id, *sessions])
    try:
        occurrence.refresh_from_db()
    except Occurrence.DoesNotExist:
        return []
    detections = occurrence.detections.select_related("source_image").order_by(*CAPTURE_ORDER)
    by_session: dict[int, list[Detection]] = {}
    for detection in detections:
        # A capture with no session stays with the earliest piece.
        if detection.source_image.event_id is not None:
            by_session.setdefault(detection.source_image.event_id, []).append(detection)
    if len(by_session) < 2:
        return []

    earliest_event_id, *later_event_ids = by_session
    pieces = [_move_to_new_occurrence(occurrence, by_session[event_id]) for event_id in later_event_ids]

    if occurrence.event_id != earliest_event_id:
        occurrence.event_id = earliest_event_id
        Occurrence.objects.filter(pk=occurrence.pk).update(event_id=earliest_event_id)

    _copy_identifications(occurrence, pieces)
    for piece in [occurrence, *pieces]:
        update_occurrence_determination(piece, save=True)
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
