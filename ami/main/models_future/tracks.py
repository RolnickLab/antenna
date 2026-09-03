"""Operations for correcting a track after tracking has grouped it.

A track is a run of detections that tracking decided are the same insect, all
attached to one occurrence and linked in time order through
``Detection.next_detection``.

Tracking errs toward leaving one animal as two occurrences rather than merging
two animals into one, because a wrong merge destroys a record that no later
step recovers. These operations are the repair for the merges it still gets
wrong: cut a track in two, or pull a single detection out of it.

Both operations work on the occurrence's detections in timestamp order, which is
what the occurrence view shows, and repair the chain links to match. That means
they behave sensibly on occurrences that were never tracked and so carry no
links at all.
"""

from __future__ import annotations

from django.db import transaction

from ami.main.models import Detection, Occurrence


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

    occurrence.save()
    new_occurrence.save()
    return new_occurrence
