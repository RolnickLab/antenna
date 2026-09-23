"""Payload schemas for an occurrence's history records, one per subtype.

A record's ``payload`` is JSON, so these schemas are what keeps each subtype's shape
fixed: every write validates against the schema for its kind and subtype.
"""

import datetime

import pydantic


class HistoryPayload(pydantic.BaseModel):
    class Config:
        extra = "forbid"


class DeterminationChangePayload(HistoryPayload):
    # The occurrence's determination before and after the run, as taxon ids. Equal
    # when the run changed predictions without moving the determination.
    taxon_before_id: int | None = None
    taxon_after_id: int | None = None


class TrackingResultPayload(DeterminationChangePayload):
    # The tunables the run used, as the tracking config holds them, without its scope.
    settings: dict = {}
    feature_algorithm_id: int | None = None
    detections_count: int
    frames_linked: int
    occurrences_merged: list[int] = []
    cost_mean: float | None = None
    cost_max: float | None = None


class ClassMaskingResultPayload(DeterminationChangePayload):
    taxa_list_id: int
    source_algorithm_id: int
    detection_ids: list[int]


class SizeFilterResultPayload(DeterminationChangePayload):
    size_threshold: float
    detection_ids: list[int]


class TrackCompleteReviewPayload(HistoryPayload):
    detection_ids: list[int]
    frames_count: int
    first_timestamp: datetime.datetime | None = None
    last_timestamp: datetime.datetime | None = None
    # Compared with the previous track_complete review; the first review lists none.
    detections_added: list[int] = []
    detections_removed: list[int] = []
    # The occurrence reviewed. A merge moves reviews onto the surviving occurrence, and
    # only its own reviews are compared with a later confirmation of it.
    occurrence_id: int | None = None
    # Set when regrouping split a confirmed occurrence at a session boundary: the
    # confirmation carries over to each piece, restated for the piece's own detections.
    split_from_occurrence_id: int | None = None


# Keyed by (kind, subtype). A subtype missing here cannot be written.
HISTORY_PAYLOAD_SCHEMAS: dict[tuple[str, str], type[HistoryPayload]] = {
    ("algorithm_result", "tracking"): TrackingResultPayload,
    ("algorithm_result", "class_masking"): ClassMaskingResultPayload,
    ("algorithm_result", "size_filter"): SizeFilterResultPayload,
    ("review", "track_complete"): TrackCompleteReviewPayload,
}


def validate_history_payload(kind: str, subtype: str, payload: dict | HistoryPayload) -> dict:
    """The payload as JSON-ready data, or a ValueError when it does not fit its subtype's schema."""
    schema = HISTORY_PAYLOAD_SCHEMAS.get((kind, subtype))
    if schema is None:
        raise ValueError(f"No history payload schema for kind={kind!r} subtype={subtype!r}")
    if isinstance(payload, HistoryPayload) and not isinstance(payload, schema):
        raise ValueError(f"{type(payload).__name__} is not the payload schema for {kind}/{subtype}")
    data = payload.dict() if isinstance(payload, HistoryPayload) else payload
    # Round-trip through JSON so datetimes are stored as ISO strings.
    return pydantic.parse_raw_as(dict, schema.parse_obj(data).json())
