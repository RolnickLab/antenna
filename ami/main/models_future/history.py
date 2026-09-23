"""An occurrence's history: what algorithms and people did to it, newest first.

Algorithm results and reviews are ``OccurrenceHistoryRecord`` rows. Identifications and
predictions keep their own tables, and ``occurrence_timeline`` merges all of them into one
list for the history endpoint.
"""

from __future__ import annotations

import datetime

from django.utils import timezone

from ami.main.models import Detection, Occurrence, OccurrenceHistoryRecord, User
from ami.main.schemas import TrackCompleteReviewPayload

TRACK_COMPLETE = "track_complete"


def latest_track_complete_review(occurrence: Occurrence) -> OccurrenceHistoryRecord | None:
    return (
        OccurrenceHistoryRecord.objects.filter(
            occurrence=occurrence, kind=OccurrenceHistoryRecord.Kind.REVIEW, subtype=TRACK_COMPLETE
        )
        .order_by("-timestamp", "-pk")
        .first()
    )


def record_track_complete_review(
    occurrence: Occurrence, user: User, timestamp: datetime.datetime | None = None
) -> OccurrenceHistoryRecord | None:
    """Record that ``user`` confirmed this occurrence's detections, unless they are the set last confirmed.

    Re-confirming an unchanged track adds nothing to the history, so the review list shows
    only the sets a person actually looked at. The first review always posts.
    """
    frames = list(
        Detection.objects.valid()
        .filter(occurrence=occurrence)
        .order_by("source_image__timestamp", "pk")
        .values_list("pk", "source_image_id", "source_image__timestamp")
    )
    detection_ids = sorted(pk for pk, _, _ in frames)
    previous = latest_track_complete_review(occurrence)
    previous_ids = sorted(previous.payload.get("detection_ids", [])) if previous else None
    if previous_ids == detection_ids:
        return None

    capture_times = [captured for _, _, captured in frames if captured is not None]
    payload = TrackCompleteReviewPayload(
        detection_ids=detection_ids,
        frames_count=len({capture_id for _, capture_id, _ in frames}),
        first_timestamp=min(capture_times, default=None),
        last_timestamp=max(capture_times, default=None),
        detections_added=sorted(set(detection_ids) - set(previous_ids)) if previous_ids is not None else [],
        detections_removed=sorted(set(previous_ids) - set(detection_ids)) if previous_ids is not None else [],
    )
    record = OccurrenceHistoryRecord.build(
        occurrence_id=occurrence.pk,
        kind=OccurrenceHistoryRecord.Kind.REVIEW,
        subtype=TRACK_COMPLETE,
        payload=payload,
        timestamp=timestamp or timezone.now(),
        user=user,
    )
    record.save()
    return record
