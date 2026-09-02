"""Operations for correcting a track after tracking has grouped it.

A track is a run of detections that tracking decided are the same insect, all
attached to one occurrence and linked in time order through
``Detection.next_detection``.

Tracking errs toward leaving one animal as two occurrences rather than merging
two animals into one, because a wrong merge destroys a record that no later
step recovers. These operations are the repair for the merges it still gets
wrong: cut a track in two, or pull a single detection out of it.

All operations work on the occurrence's detections in timestamp order, which is
what the occurrence view shows, and repair the chain links to match. That means
they behave sensibly on occurrences that were never tracked and so carry no
links at all.

Two invariants hold after every operation here:

- A chain link never crosses an occurrence boundary. Otherwise a later tracking
  pass would walk the chain, decide both occurrences are one, and undo the edit.
- An edit that changes which detections an occurrence holds clears its grouping
  verification. A person confirmed the set they were shown, not a later one.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from ami.main.models import Detection, Identification, Occurrence, User


class TrackEditError(ValueError):
    """A track edit that cannot be applied to this occurrence and detection."""


def _ordered_detections(occurrence: Occurrence) -> list[Detection]:
    return list(occurrence.detections.order_by("timestamp", "pk"))


def _move_to_new_occurrence(occurrence: Occurrence, detections: list[Detection]) -> Occurrence:
    """Attach ``detections`` to a new occurrence beside ``occurrence``."""
    new_occurrence = Occurrence.objects.create(
        event=occurrence.event,
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

    head, tail = ordered[:index], ordered[index:]

    # Cut the link across the split so the two tracks stop referring to each other.
    boundary = head[-1]
    if boundary.next_detection_id is not None:
        boundary.next_detection = None
        boundary.save(update_fields=["next_detection"])

    new_occurrence = _move_to_new_occurrence(occurrence, tail)

    _clear_verification(occurrence, new_occurrence)
    occurrence.save()
    new_occurrence.save()
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

    detection = ordered[index]
    successor_id = detection.next_detection_id

    # Stitch the chain across the removed detection before moving it, so the
    # remaining detections stay one track rather than two.
    if index > 0:
        predecessor = ordered[index - 1]
        if predecessor.next_detection_id == detection.pk:
            # Clear the outbound link first: next_detection is unique, so writing
            # the successor onto the predecessor while the detection still points
            # at it would violate the constraint.
            detection.next_detection = None
            detection.save(update_fields=["next_detection"])
            predecessor.next_detection_id = successor_id
            predecessor.save(update_fields=["next_detection"])
    if detection.next_detection_id is not None:
        detection.next_detection = None
        detection.save(update_fields=["next_detection"])

    new_occurrence = _move_to_new_occurrence(occurrence, [detection])

    _clear_verification(occurrence, new_occurrence)
    occurrence.save()
    new_occurrence.save()
    return new_occurrence


def _cut_links_leaving(occurrence: Occurrence) -> None:
    """Clear every chain link that would cross this occurrence's boundary.

    A link between detections in different occurrences would let a later tracking
    pass walk the chain and fold the two back together, silently undoing a human
    edit. Called after any operation that moves detections.
    """
    members = set(occurrence.detections.values_list("pk", flat=True))
    if not members:
        return

    outbound = Detection.objects.filter(pk__in=members, next_detection__isnull=False).exclude(
        next_detection_id__in=members
    )
    outbound.update(next_detection=None)

    inbound = Detection.objects.filter(next_detection_id__in=members).exclude(pk__in=members)
    inbound.update(next_detection=None)


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

    _absorb(target, sources)
    _cut_links_leaving(target)
    _clear_verification(target)
    target.save()
    return target


@transaction.atomic
def add_detections(target: Occurrence, detections: Iterable[Detection]) -> Occurrence:
    """Move individual detections into ``target``.

    Use when a frame belongs to this animal but landed on its own or on the wrong
    occurrence. Any occurrence left with no detections is absorbed rather than
    deleted outright, so identifications on it survive.
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

    donors = list(Occurrence.objects.filter(pk__in=donor_pks))
    Detection.objects.filter(pk__in=[d.pk for d in detections]).update(occurrence=target)

    emptied = [o for o in donors if not o.detections.exists()]
    _absorb(target, emptied)

    _cut_links_leaving(target)
    remaining = [o for o in donors if o.pk not in {e.pk for e in emptied}]
    for donor in remaining:
        _cut_links_leaving(donor)
        donor.save()

    _clear_verification(target, *remaining)
    target.save()
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
