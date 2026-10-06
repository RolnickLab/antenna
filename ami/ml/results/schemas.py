"""What each kind of algorithm result records: one pydantic model per kind, and the registry of kinds.

A kind's model holds only what its run alone knows; settings live on the job, and the new taxon on
the classifications the run created. ``extra`` takes whatever else a method returns and is never read
for logic. This is the only module that calls pydantic's API for results, and it imports nothing from
Django, so models, writers, serializers and settings can all import it. Adding a kind = a model with its
``kind`` + an entry in ``ALGORITHM_RESULT_DATA_MODELS``; see README.md in this package.
The field helpers below also read post-processing task config schemas, which declare setting titles and
references the same way.
"""

import json
from typing import Any, ClassVar

import pydantic


def reference(ref_type: str, default: Any = None, **field_options: Any) -> Any:
    """Declare a settings field that holds another record's id; the history resolves it to ``{type, id, name}``.

    Used by post-processing task config schemas; ``field_options`` go to ``pydantic.Field``.
    """
    return pydantic.Field(default, reference=ref_type, **field_options)


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


class TrackingResultData(DeterminationSnapshot):
    """Figures from the detections the run linked into the occurrence, in capture order."""

    kind: ClassVar[str] = "tracking"

    detection_count: int
    # Mean distance per step between consecutive detection centres, as a fraction of the image diagonal;
    # 0 for one detection.
    motion: float
    # The same distances added up over the whole path, as a fraction of the image diagonal.
    path_length: float
    # The largest box area over the smallest (at least 1), with areas floored at 1; 1 when the box never changed size.
    size_change: float
    # Distinct taxa among the machine classifications of the occurrence's detections, leaving out post-processing ones.
    distinct_taxa: int
    # The share of those classifications naming the determination after the run; None when there are none.
    label_agreement: float | None = None
    # The matching cost of each link this run made in the chain, rounded to 4 places, in chain order.
    link_costs: list[float] = []
    # Occurrences the run folded into this one. They are deleted, so these are plain ids, not references.
    merged_occurrence_ids: list[int] = []


ALGORITHM_RESULT_DATA_MODELS: tuple[type[AlgorithmResultData], ...] = (
    ClassMaskingResultData,
    SizeFilterResultData,
    TrackingResultData,
)

ALGORITHM_RESULT_DATA_SCHEMAS: dict[str, type[AlgorithmResultData]] = {
    model.kind: model for model in ALGORITHM_RESULT_DATA_MODELS
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


def result_value(kind: str, data: dict) -> float | None:
    """The figure the kind's ``value_field`` names in validated ``data``, which a result stores as ``value``."""
    field = _schema_for(kind).value_field
    return data.get(field) if field else None


def field_references(model: type[pydantic.BaseModel]) -> dict[str, str]:
    """The model's fields declared with ``reference()``, mapped to the reference type."""
    return {
        name: field.field_info.extra["reference"]
        for name, field in model.__fields__.items()
        if "reference" in field.field_info.extra
    }


def field_titles(model: type[pydantic.BaseModel]) -> dict[str, str | None]:
    """Every field of the model, in declaration order, mapped to its ``title`` or None."""
    return {name: field.field_info.title for name, field in model.__fields__.items()}
