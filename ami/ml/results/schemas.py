"""The base for what each kind of algorithm result records, and the registry of kinds.

A kind's model holds only what its run alone knows; the run's config lives on the job, and the new
taxon on the classifications the run created. ``extra`` takes whatever else a method returns and is
never read for logic. It imports nothing from Django, so models, writers and serializers can all
import it. A kind's model lives with the task that writes it and is listed in the task's
``result_models``; see README.md in this package.
"""

import functools
import json
from typing import Any, ClassVar

import pydantic


class AlgorithmResultData(pydantic.BaseModel):
    # The kind this model validates; each concrete model sets it, and the registry is keyed by it.
    kind: ClassVar[str]
    # The data field the result's ``value`` repeats, for filtering and sorting; None for no value.
    value_field: ClassVar[str | None] = None

    # Stored and returned by the API only, never read for logic; a value a feature needs becomes a typed field.
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


@functools.cache
def result_data_models() -> dict[str, type[AlgorithmResultData]]:
    """Every result kind, from the ``result_models`` the post-processing tasks declare, keyed by kind."""
    from ami.ml.post_processing.registry import POSTPROCESSING_TASKS

    models: dict[str, type[AlgorithmResultData]] = {}
    for task in POSTPROCESSING_TASKS.values():
        for model in task.result_models:
            if models.setdefault(model.kind, model) is not model:
                raise ValueError(f"Result kind {model.kind!r} is declared by two different data models.")
    return models


def _schema_for(kind: str) -> type[AlgorithmResultData]:
    schema = result_data_models().get(kind)
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
