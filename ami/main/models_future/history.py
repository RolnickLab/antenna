"""An occurrence's history: what algorithms and people did to it, newest first.

What a job decided about an occurrence is an ``AlgorithmResult`` and what a person said about
it is a ``ValidationReview``. Identifications and predictions keep their own tables, and
``occurrence_timeline`` merges all four into one list for the history endpoint.
"""

from __future__ import annotations

import dataclasses
import datetime
import typing
from collections.abc import Iterable

from django.db.models import Case, F, Value, When

from ami.main.models import (
    AlgorithmResult,
    Classification,
    Detection,
    Identification,
    Occurrence,
    Taxon,
    User,
    ValidationReview,
)
from ami.main.schemas import GroupingReviewPayload

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models import Algorithm

GROUPING = ValidationReview.Aspect.GROUPING
COMMENT = ValidationReview.Aspect.COMMENT


def latest_track_complete_review(occurrence: Occurrence) -> ValidationReview | None:
    """The latest grouping review written for this occurrence, ignoring reviews a merge brought in."""
    return (
        ValidationReview.objects.filter(occurrence=occurrence, aspect=GROUPING, payload__occurrence_id=occurrence.pk)
        .order_by("-timestamp", "-pk")
        .first()
    )


def edited_since_track_complete_review(occurrence: Occurrence) -> bool:
    """Whether the occurrence's detections differ from those its latest own review confirmed."""
    review = latest_track_complete_review(occurrence)
    if review is None:
        return False
    current = set(Detection.objects.valid().filter(occurrence=occurrence).values_list("pk", flat=True))
    return current != set(review.payload["detection_ids"])


def latest_tracking_result(occurrence: Occurrence) -> AlgorithmResult | None:
    """The current tracking result for this occurrence, which a grouping review answers."""
    return (
        AlgorithmResult.objects.filter(occurrence=occurrence, kind=AlgorithmResult.Kind.TRACKING, is_current=True)
        .order_by("-timestamp", "-pk")
        .first()
    )


def record_track_complete_review(
    occurrence: Occurrence, user: User, timestamp: datetime.datetime
) -> ValidationReview | None:
    """Record that ``user`` confirmed this occurrence's detections at ``timestamp``.

    Nothing is written when the person's current review of this occurrence already confirms
    the same detections, so re-confirming an unchanged track, or replaying a confirmation,
    adds no row. Otherwise the new review replaces that person's current one.
    """
    review = _build_grouping_review(occurrence, user.pk, timestamp, latest_track_complete_review(occurrence))
    own_current = (
        ValidationReview.objects.filter(
            occurrence=occurrence,
            aspect=GROUPING,
            user=user,
            is_current=True,
            payload__occurrence_id=occurrence.pk,
        )
        .order_by("-timestamp", "-pk")
        .first()
    )
    if (
        own_current is not None
        and not own_current.withdrawn
        and sorted(own_current.payload["detection_ids"]) == review.payload["detection_ids"]
    ):
        return None
    review.reviewed_result = latest_tracking_result(occurrence)
    _retire_current_grouping_reviews(occurrence, user_ids=[user.pk])
    review.save()
    return review


def withdraw_track_complete_reviews(occurrence: Occurrence) -> int:
    """Mark the occurrence's standing grouping reviews withdrawn, as unconfirming it does."""
    return ValidationReview.objects.filter(
        occurrence=occurrence, aspect=GROUPING, is_current=True, withdrawn=False
    ).update(withdrawn=True)


def retire_grouping_reviews(occurrence_pks: Iterable[int]) -> int:
    """Stop the grouping reviews of occurrences whose detections just changed from standing.

    They confirmed a set of detections the occurrence no longer holds. They stay in the
    history and are still what ``edited_since_track_complete_review`` compares against.
    """
    return ValidationReview.objects.filter(
        occurrence_id__in=list(occurrence_pks), aspect=GROUPING, is_current=True
    ).update(is_current=False)


def carry_confirmation_over_split(occurrence: Occurrence, pieces: list[Occurrence]) -> None:
    """Restate a confirmed occurrence's review for each piece a session split left.

    Each review keeps the original reviewer and time but lists only its piece's
    detections, so a later re-confirmation of a piece compares against what it holds.
    """
    if occurrence.grouping_verified_at is None:
        return
    _retire_current_grouping_reviews(occurrence, user_ids=[occurrence.grouping_verified_by_id])
    ValidationReview.objects.bulk_create(
        _build_grouping_review(
            piece,
            occurrence.grouping_verified_by_id,
            occurrence.grouping_verified_at,
            previous=None,
            split_from_occurrence_id=occurrence.pk,
        )
        for piece in [occurrence, *pieces]
    )


def move_history(source_pks: Iterable[int], target: Occurrence) -> None:
    """Move results and reviews off occurrences being merged into ``target``.

    Moved rows stop being current, so they stay in the target's history without standing
    for it; comments have no current row to replace and keep their state.
    """
    source_pks = list(source_pks)
    if not source_pks:
        return
    AlgorithmResult.objects.filter(occurrence_id__in=source_pks).update(occurrence=target, is_current=False)
    ValidationReview.objects.filter(occurrence_id__in=source_pks).update(
        occurrence=target,
        is_current=Case(When(aspect=COMMENT, then=F("is_current")), default=Value(False)),
    )


def _retire_current_grouping_reviews(occurrence: Occurrence, user_ids: list[int | None]) -> None:
    ValidationReview.objects.filter(
        occurrence=occurrence, aspect=GROUPING, is_current=True, user_id__in=[u for u in user_ids if u is not None]
    ).update(is_current=False)


def _build_grouping_review(
    occurrence: Occurrence,
    user_id: int | None,
    timestamp: datetime.datetime,
    previous: ValidationReview | None,
    split_from_occurrence_id: int | None = None,
) -> ValidationReview:
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
    payload = GroupingReviewPayload(
        detection_ids=detection_ids,
        frames_count=len({capture_id for _, capture_id, _ in frames}),
        first_timestamp=min(capture_times, default=None),
        last_timestamp=max(capture_times, default=None),
        detections_added=sorted(set(detection_ids) - previous_ids),
        detections_removed=sorted(previous_ids - set(detection_ids)),
        occurrence_id=occurrence.pk,
        split_from_occurrence_id=split_from_occurrence_id,
    )
    return ValidationReview(
        occurrence=occurrence,
        user_id=user_id,
        aspect=GROUPING,
        verdict=ValidationReview.Verdict.CONFIRMED,
        payload=payload.dict(),
        timestamp=timestamp,
    )


def add_comment(occurrence: Occurrence, user: User, comment: str) -> ValidationReview:
    """Leave a note on an occurrence: a review with ``aspect = comment`` and no verdict."""
    return ValidationReview.objects.create(occurrence=occurrence, user=user, aspect=COMMENT, comment=comment)


@dataclasses.dataclass
class TimelineEntry:
    """One entry of the merged history, in the shape ``OccurrenceHistoryEntrySerializer`` reads."""

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
    verdict: str | None = None
    comment: str = ""
    withdrawn: bool = False
    is_current: bool | None = None


def review_entry(review: ValidationReview) -> TimelineEntry:
    return TimelineEntry(
        type="review",
        id=review.pk,
        timestamp=review.timestamp,
        subtype=review.aspect,
        user=review.user,
        payload=review.payload,
        verdict=review.verdict,
        comment=review.comment,
        withdrawn=review.withdrawn,
        is_current=review.is_current,
    )


def occurrence_timeline(occurrence: Occurrence) -> list[TimelineEntry]:
    """Results, reviews, identifications and predictions of one occurrence, merged newest first.

    Each algorithm contributes one prediction, its best. A prediction made by an algorithm
    that also left a result here is left out: the result already stands for that change and
    names the taxon before and after. The query count does not grow with the entries.
    """
    results = list(
        AlgorithmResult.objects.filter(occurrence=occurrence)
        .select_related("algorithm", "job")
        .order_by("-timestamp", "-pk")
    )
    taxon_ids = {
        (result.data or {}).get(key)
        for result in results
        for key in ("taxon_before_id", "taxon_after_id")
        if (result.data or {}).get(key) is not None
    }
    taxa = {taxon.pk: taxon for taxon in Taxon.objects.filter(pk__in=taxon_ids)} if taxon_ids else {}

    entries = [
        TimelineEntry(
            type="algorithm_result",
            id=result.pk,
            timestamp=result.timestamp,
            subtype=result.kind,
            algorithm=result.algorithm,
            job=result.job,
            taxon=taxa.get((result.data or {}).get("taxon_after_id")),
            taxon_before=taxa.get((result.data or {}).get("taxon_before_id")),
            score=result.value,
            payload=result.data or {},
            is_current=result.is_current,
        )
        for result in results
    ]

    reviews = ValidationReview.objects.filter(occurrence=occurrence).select_related("user")
    entries.extend(review_entry(review) for review in reviews)

    identifications = Identification.objects.filter(occurrence=occurrence).select_related("user", "taxon")
    entries.extend(
        TimelineEntry(
            type="identification",
            id=identification.pk,
            timestamp=identification.created_at,
            user=identification.user,
            taxon=identification.taxon,
            comment=identification.comment or "",
            withdrawn=identification.withdrawn,
            payload={
                "comment": identification.comment,
                "withdrawn": identification.withdrawn,
                "agreed_with_identification_id": identification.agreed_with_identification_id,
                "agreed_with_prediction_id": identification.agreed_with_prediction_id,
            },
        )
        for identification in identifications
    )

    folded = {result.algorithm_id for result in results}
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
        for prediction in _one_prediction_per_algorithm(occurrence)
        if prediction.algorithm_id not in folded
    )

    entries.sort(key=lambda entry: (entry.timestamp, entry.id), reverse=True)
    return entries


def _one_prediction_per_algorithm(occurrence: Occurrence) -> list[Classification]:
    """The best prediction of each algorithm: highest score, then terminal, then latest.

    ``Occurrence.predictions()`` keeps every classification tied for an algorithm's top
    score, which would show the same prediction once per detection.
    """

    def rank(prediction: Classification) -> tuple:
        score = prediction.score if prediction.score is not None else float("-inf")
        return (score, prediction.terminal, prediction.created_at, prediction.pk)

    best: dict[int | None, Classification] = {}
    for prediction in occurrence.predictions():
        current = best.get(prediction.algorithm_id)
        if current is None or rank(prediction) > rank(current):
            best[prediction.algorithm_id] = prediction
    return list(best.values())
