"""Shapes of the JSON on algorithm results and validation reviews, one per kind or aspect.

``AlgorithmResult.data`` and ``ValidationReview.payload`` are JSON, so these schemas keep each
kind's shape fixed: every write validates against the schema registered for it, and a kind or
aspect with no schema cannot carry JSON.
"""

import datetime

import pydantic


class OutputPayload(pydantic.BaseModel):
    class Config:
        extra = "forbid"


class DeterminationChangeData(OutputPayload):
    # The occurrence's determination before and after the run, as taxon ids. Equal
    # when the run changed predictions without moving the determination.
    taxon_before_id: int | None = None
    taxon_after_id: int | None = None


class TrackingResultData(DeterminationChangeData):
    # The tunables the run used, as the tracking config holds them, without its scope.
    settings: dict = {}
    feature_algorithm_id: int | None = None
    detections_count: int
    frames_linked: int
    occurrences_merged: list[int] = []
    cost_mean: float | None = None
    cost_max: float | None = None


class ClassMaskingResultData(DeterminationChangeData):
    taxa_list_id: int
    source_algorithm_id: int
    detection_ids: list[int]


class SizeFilterResultData(DeterminationChangeData):
    size_threshold: float
    detection_ids: list[int]


class GroupingReviewPayload(OutputPayload):
    detection_ids: list[int]
    frames_count: int
    first_timestamp: datetime.datetime | None = None
    last_timestamp: datetime.datetime | None = None
    # Compared with the occurrence's previous grouping review; the first review lists none.
    detections_added: list[int] = []
    detections_removed: list[int] = []
    # The occurrence reviewed. A merge moves reviews onto the surviving occurrence, and
    # only its own reviews are compared with a later confirmation of it.
    occurrence_id: int | None = None
    # Set when regrouping split a confirmed occurrence at a session boundary: the
    # confirmation carries over to each piece, restated for the piece's own detections.
    split_from_occurrence_id: int | None = None


class CommentReviewPayload(OutputPayload):
    """A comment's text is in ``ValidationReview.comment``; the payload stays empty."""


# A kind missing here can carry a ``value`` but no ``data``.
ALGORITHM_RESULT_DATA_SCHEMAS: dict[str, type[OutputPayload]] = {
    "tracking": TrackingResultData,
    "class_masking": ClassMaskingResultData,
    "size_filter": SizeFilterResultData,
}

# An aspect missing here cannot be written with a payload.
VALIDATION_REVIEW_PAYLOAD_SCHEMAS: dict[str, type[OutputPayload]] = {
    "grouping": GroupingReviewPayload,
    "comment": CommentReviewPayload,
}


def _validate(schemas: dict[str, type[OutputPayload]], name: str, value: dict | OutputPayload) -> dict:
    schema = schemas.get(name)
    if schema is None:
        raise ValueError(f"No payload schema is registered for {name!r}.")
    if isinstance(value, OutputPayload) and not isinstance(value, schema):
        raise ValueError(f"{type(value).__name__} is not the payload schema for {name!r}.")
    data = value.dict() if isinstance(value, OutputPayload) else value
    # Round-trip through JSON so datetimes are stored as ISO strings.
    return pydantic.parse_raw_as(dict, schema.parse_obj(data).json())


def validate_result_data(kind: str, data: dict | OutputPayload | None) -> dict | None:
    """``data`` as JSON-ready values, or a ValueError when it does not fit the kind's schema."""
    if data is None:
        return None
    return _validate(ALGORITHM_RESULT_DATA_SCHEMAS, kind, data)


def validate_review_payload(aspect: str, payload: dict | OutputPayload | None) -> dict:
    """``payload`` as JSON-ready values, or a ValueError when it does not fit the aspect's schema.

    An empty payload is valid for every aspect that has no schema yet.
    """
    if not payload and aspect not in VALIDATION_REVIEW_PAYLOAD_SCHEMAS:
        return {}
    return _validate(VALIDATION_REVIEW_PAYLOAD_SCHEMAS, aspect, payload or {})
