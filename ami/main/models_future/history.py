"""An occurrence's history: what algorithms and people did to it, newest first.

Algorithm results and reviews are ``OccurrenceHistoryRecord`` rows. Identifications and
predictions keep their own tables, and ``occurrence_timeline`` merges all of them into one
list for the history endpoint.
"""

from __future__ import annotations

import dataclasses
import datetime
import typing

from ami.main.models import Detection, Identification, Occurrence, OccurrenceHistoryRecord, Taxon, User
from ami.main.schemas import TrackCompleteReviewPayload

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models import Algorithm

TRACK_COMPLETE = "track_complete"


def latest_track_complete_review(occurrence: Occurrence) -> OccurrenceHistoryRecord | None:
    """The latest review written for this occurrence, ignoring reviews a merge brought in."""
    return (
        OccurrenceHistoryRecord.objects.filter(
            occurrence=occurrence,
            kind=OccurrenceHistoryRecord.Kind.REVIEW,
            subtype=TRACK_COMPLETE,
            payload__occurrence_id=occurrence.pk,
        )
        .order_by("-timestamp", "-pk")
        .first()
    )


def record_track_complete_review(
    occurrence: Occurrence, user: User, timestamp: datetime.datetime, was_confirmed: bool
) -> OccurrenceHistoryRecord | None:
    """Record that ``user`` confirmed this occurrence's detections.

    Nothing is written when the same person re-confirms a still-confirmed, unchanged set,
    so the review list shows each distinct confirmation once.
    """
    previous = latest_track_complete_review(occurrence)
    record = _build_track_complete_review(occurrence, user.pk, timestamp, previous)
    if (
        was_confirmed
        and previous is not None
        and previous.user_id == user.pk
        and sorted(previous.payload["detection_ids"]) == record.payload["detection_ids"]
    ):
        return None
    record.save()
    return record


def carry_confirmation_over_split(occurrence: Occurrence, pieces: list[Occurrence]) -> None:
    """Restate a confirmed occurrence's review for each piece a session split left.

    Each review keeps the original reviewer and time but lists only its piece's
    detections, so a later re-confirmation of a piece compares against what it holds.
    """
    if occurrence.grouping_verified_at is None:
        return
    OccurrenceHistoryRecord.objects.bulk_create(
        _build_track_complete_review(
            piece,
            occurrence.grouping_verified_by_id,
            occurrence.grouping_verified_at,
            previous=None,
            split_from_occurrence_id=occurrence.pk,
        )
        for piece in [occurrence, *pieces]
    )


def _build_track_complete_review(
    occurrence: Occurrence,
    user_id: int | None,
    timestamp: datetime.datetime,
    previous: OccurrenceHistoryRecord | None,
    split_from_occurrence_id: int | None = None,
) -> OccurrenceHistoryRecord:
    """An unsaved review of the occurrence's current detections, with the change since ``previous``."""
    frames = list(
        Detection.objects.valid()
        .filter(occurrence=occurrence)
        .order_by("source_image__timestamp", "pk")
        .values_list("pk", "source_image_id", "source_image__timestamp")
    )
    detection_ids = sorted(pk for pk, _, _ in frames)
    previous_ids = set(previous.payload["detection_ids"]) if previous else set(detection_ids)
    capture_times = [captured for _, _, captured in frames if captured is not None]
    payload = TrackCompleteReviewPayload(
        detection_ids=detection_ids,
        frames_count=len({capture_id for _, capture_id, _ in frames}),
        first_timestamp=min(capture_times, default=None),
        last_timestamp=max(capture_times, default=None),
        detections_added=sorted(set(detection_ids) - previous_ids),
        detections_removed=sorted(previous_ids - set(detection_ids)),
        occurrence_id=occurrence.pk,
        split_from_occurrence_id=split_from_occurrence_id,
    )
    record = OccurrenceHistoryRecord.build(
        occurrence_id=occurrence.pk,
        kind=OccurrenceHistoryRecord.Kind.REVIEW,
        subtype=TRACK_COMPLETE,
        payload=payload,
        timestamp=timestamp,
    )
    record.user_id = user_id
    return record


@dataclasses.dataclass
class TimelineEntry:
    """One entry of the merged history, in the shape ``OccurrenceTimelineEntrySerializer`` reads."""

    type: str
    id: int
    timestamp: datetime.datetime
    subtype: str | None = None
    user: User | None = None
    algorithm: Algorithm | None = None
    job: Job | None = None
    taxon: Taxon | None = None
    taxon_before: Taxon | None = None
    score: float | None = None
    payload: dict = dataclasses.field(default_factory=dict)


def occurrence_timeline(occurrence: Occurrence) -> list[TimelineEntry]:
    """History records, identifications and predictions of one occurrence, merged newest first.

    A prediction made by an algorithm that also left a history record here is left out: the
    record already stands for that change and names the taxon before and after. Costs four
    queries whatever the number of entries.
    """
    records = list(
        OccurrenceHistoryRecord.objects.filter(occurrence=occurrence)
        .select_related("user", "algorithm", "job")
        .order_by("-timestamp", "-pk")
    )
    taxon_ids = {
        record.payload.get(key)
        for record in records
        for key in ("taxon_before_id", "taxon_after_id")
        if record.payload.get(key) is not None
    }
    taxa = {taxon.pk: taxon for taxon in Taxon.objects.filter(pk__in=taxon_ids)} if taxon_ids else {}

    entries = [
        TimelineEntry(
            type=record.kind,
            id=record.pk,
            timestamp=record.timestamp,
            subtype=record.subtype,
            user=record.user,
            algorithm=record.algorithm,
            job=record.job,
            taxon=taxa.get(record.payload.get("taxon_after_id")),
            taxon_before=taxa.get(record.payload.get("taxon_before_id")),
            payload=record.payload,
        )
        for record in records
    ]

    identifications = Identification.objects.filter(occurrence=occurrence).select_related("user", "taxon")
    entries.extend(
        TimelineEntry(
            type="identification",
            id=identification.pk,
            timestamp=identification.created_at,
            user=identification.user,
            taxon=identification.taxon,
            payload={
                "comment": identification.comment,
                "withdrawn": identification.withdrawn,
                "agreed_with_identification_id": identification.agreed_with_identification_id,
                "agreed_with_prediction_id": identification.agreed_with_prediction_id,
            },
        )
        for identification in identifications
    )

    folded = {record.algorithm_id for record in records if record.algorithm_id is not None}
    entries.extend(
        TimelineEntry(
            type="prediction",
            id=prediction.pk,
            timestamp=prediction.created_at,
            algorithm=prediction.algorithm,
            taxon=prediction.taxon,
            score=prediction.score,
            payload={
                "detection_id": prediction.detection_id,
                "terminal": prediction.terminal,
                "applied_to_id": prediction.applied_to_id,
            },
        )
        for prediction in occurrence.predictions()
        if prediction.algorithm_id not in folded
    )

    entries.sort(key=lambda entry: (entry.timestamp, entry.id), reverse=True)
    return entries
