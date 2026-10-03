"""Shapes of the JSON on algorithm results and validation reviews, one per kind or aspect.

``AlgorithmResult.data`` and ``ValidationReview.payload`` are JSON columns, so these schemas keep
each kind's shape fixed: every write validates against the schema registered for it, and a kind
or aspect with no schema cannot be written.
"""

import pydantic


class OutputPayload(pydantic.BaseModel):
    class Config:
        extra = "forbid"


class DeterminationChangeData(OutputPayload):
    # The occurrence's determination before and after the run, as taxon ids. Equal when the
    # run changed predictions without moving the determination.
    taxon_before_id: int | None = None
    taxon_after_id: int | None = None


class ClassMaskingResultData(DeterminationChangeData):
    taxa_list_id: int
    source_algorithm_id: int
    detection_ids: list[int]


class SizeFilterResultData(DeterminationChangeData):
    size_threshold: float
    detection_ids: list[int]


class CommentReviewPayload(OutputPayload):
    """A comment's text is in ``ValidationReview.comment``; the payload stays empty."""


ALGORITHM_RESULT_DATA_SCHEMAS: dict[str, type[OutputPayload]] = {
    "class_masking": ClassMaskingResultData,
    "size_filter": SizeFilterResultData,
}

VALIDATION_REVIEW_PAYLOAD_SCHEMAS: dict[str, type[OutputPayload]] = {
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


def validate_result_data(kind: str, data: dict | OutputPayload | None) -> dict:
    """``data`` as JSON-ready values, or a ValueError when it does not fit the kind's schema."""
    return _validate(ALGORITHM_RESULT_DATA_SCHEMAS, kind, data or {})


def validate_review_payload(aspect: str, payload: dict | OutputPayload | None) -> dict:
    """``payload`` as JSON-ready values, or a ValueError when it does not fit the aspect's schema."""
    return _validate(VALIDATION_REVIEW_PAYLOAD_SCHEMAS, aspect, payload or {})
