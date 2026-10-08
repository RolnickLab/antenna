"""What each kind of algorithm result records: one pydantic model per kind, and the registry of kinds.

A kind's model holds only what its run alone knows; the run's config lives on the job, and the new
taxon on the classifications the run created. ``extra`` takes whatever else a method returns and is
never read for logic. It imports nothing from Django, so models, writers and serializers can all
import it. Adding a kind = a model with its
``kind`` + an entry in ``ALGORITHM_RESULT_DATA_MODELS``; see README.md in this package.
"""

import json
from typing import Any, ClassVar

import pydantic


class AlgorithmResultData(pydantic.BaseModel):
    # The kind this model validates; each concrete model sets it, and the registry is keyed by it.
    kind: ClassVar[str]
    # The data field the result's ``value`` repeats, for filtering and sorting; None for no value.
    value_field: ClassVar[str | None] = None

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

    kind: ClassVar[str] = "class_masking"
    value_field: ClassVar[str | None] = "excluded_probability"

    # One minus the kept mass of the unmasked softmax: what the list removed, not an out-of-distribution score.
    excluded_probability: float
    # Where the class that wins after masking ranked before it; 1 means it was already the top.
    new_winner_original_rank: int | None = None


class SizeFilterResultData(DeterminationSnapshot):
    """Figures from the occurrence's smallest filtered detection."""

    kind: ClassVar[str] = "size_filter"
    value_field: ClassVar[str | None] = "relative_size"

    # The detection's box area as a fraction of its image.
    relative_size: float


ALGORITHM_RESULT_DATA_MODELS: tuple[type[AlgorithmResultData], ...] = (ClassMaskingResultData, SizeFilterResultData)

ALGORITHM_RESULT_DATA_SCHEMAS: dict[str, type[AlgorithmResultData]] = {
    model.kind: model for model in ALGORITHM_RESULT_DATA_MODELS
}


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


def result_value(kind: str, data: dict) -> float | None:
    """The figure the kind's ``value_field`` names in validated ``data``, which a result stores as ``value``."""
    field = _schema_for(kind).value_field
    return data.get(field) if field else None
