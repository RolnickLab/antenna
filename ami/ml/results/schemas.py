"""What each kind of algorithm result records: one pydantic model per kind, and the registry of kinds.

A kind's model holds only what its run alone knows; settings live on the job, and the new taxon on
the classifications the run created. ``extra`` takes whatever else a method returns and is never read
for logic. This is the only module that calls pydantic's API for results, and it imports nothing from
Django, so models, writers and serializers can all import it. Adding a kind = a model + a registry entry.
"""

import json
from typing import Any

import pydantic


def reference(ref_type: str, default: Any = None) -> Any:
    """Declare a data field that holds another record's id; the history resolves it to ``{type, id, name}``."""
    return pydantic.Field(default, reference=ref_type)


class AlgorithmResultData(pydantic.BaseModel):
    # Stored, shown and exported only, never read for logic; a value a feature needs becomes a typed field.
    extra: dict[str, Any] = {}

    @pydantic.validator("extra")
    def _extra_is_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(value))

    class Config:
        extra = "forbid"


class DeterminationSnapshot(AlgorithmResultData):
    # The occurrence's determination before and after the run, as taxon ids; equal when it did not move.
    determination_before_id: int | None = None
    determination_after_id: int | None = None


class ClassMaskingResultData(DeterminationSnapshot):
    """Figures from the occurrence's winning detection: the one whose masked classification scores highest."""

    # One minus the kept mass of the unmasked softmax: what the list removed, not an out-of-distribution score.
    excluded_probability: float
    # Where the class that wins after masking ranked before it; 1 means it was already the top.
    new_winner_original_rank: int | None = None


class SizeFilterResultData(DeterminationSnapshot):
    """Figures from the occurrence's smallest filtered detection."""

    # The detection's box area as a fraction of its image.
    relative_size: float


ALGORITHM_RESULT_DATA_SCHEMAS: dict[str, type[AlgorithmResultData]] = {
    "class_masking": ClassMaskingResultData,
    "size_filter": SizeFilterResultData,
}


def result_kinds() -> list[str]:
    return list(ALGORITHM_RESULT_DATA_SCHEMAS)


def _schema_for(kind: str) -> type[AlgorithmResultData]:
    schema = ALGORITHM_RESULT_DATA_SCHEMAS.get(kind)
    if schema is None:
        raise ValueError(f"No result data model is registered for {kind!r}.")
    return schema


def validate_result_data(kind: str, data: dict | AlgorithmResultData | None) -> dict:
    """``data`` as JSON-ready values, or a ValueError when it does not fit the kind's model."""
    schema = _schema_for(kind)
    if isinstance(data, AlgorithmResultData) and not isinstance(data, schema):
        raise ValueError(f"{type(data).__name__} is not the result data model for {kind!r}.")
    values = data.dict() if isinstance(data, AlgorithmResultData) else (data or {})
    # Round-trip through JSON so datetimes are stored as ISO strings.
    return json.loads(schema.parse_obj(values).json())


def reference_fields(kind: str) -> dict[str, str]:
    """The kind's data fields that hold another record's id, mapped to the reference type."""
    schema = _schema_for(kind)
    return {
        name: field.field_info.extra["reference"]
        for name, field in schema.__fields__.items()
        if "reference" in field.field_info.extra
    }


def data_json_schema(kind: str) -> dict:
    """The kind's data model as a JSON schema, for its OpenAPI component."""
    return _schema_for(kind).schema()
