"""The shape of ``AlgorithmResult.data``, one pydantic model per result kind.

Each model records only what the run alone knows: figures computed while it ran and the
occurrence's determination before and after, which cannot be derived later. Anything that lives
elsewhere is left out: the settings are on the job, the classifications a run created point at
the result, and the new taxon is on those classifications. ``extra`` takes whatever else a
method or processing service returns. Nothing reads ``extra`` for logic: it is stored, shown and
exported only. When a feature needs a value from it, that value becomes a typed field.

Adding a kind means adding a model here and registering it in ``ALGORITHM_RESULT_DATA_SCHEMAS``;
tracking (merges, statistics) and rank roll-ups (``rank_rollup``) are the next ones expected.
"""

import json
from typing import Any

import pydantic


class ResultData(pydantic.BaseModel):
    # Whatever else the method returned. Stored, shown and exported only, never read for logic;
    # a value a feature needs is promoted to a typed field on the kind's model.
    extra: dict[str, Any] = {}

    @pydantic.validator("extra")
    def _extra_is_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(value))

    class Config:
        extra = "forbid"


class DeterminationSnapshot(ResultData):
    # The occurrence's determination before and after the run, as taxon ids. Equal when the
    # run changed predictions without moving the determination.
    determination_before_id: int | None = None
    determination_after_id: int | None = None


class ClassMaskingResultData(DeterminationSnapshot):
    """Figures from the occurrence's winning detection: the one whose masked classification scores highest."""

    # The share of the source classifier's probability outside the species list: one minus the
    # kept mass of the unmasked softmax. A measure of what the list removed, not an
    # out-of-distribution score.
    excluded_probability: float
    # The source classifier's top prediction before masking.
    original_taxon_id: int | None = None
    original_score: float | None = None
    # Where the class that wins after masking ranked before it; 1 means it was already the top.
    new_winner_original_rank: int | None = None


class SizeFilterResultData(DeterminationSnapshot):
    """Figures from the occurrence's smallest filtered detection."""

    # The detection's box area as a fraction of its image.
    relative_size: float


ALGORITHM_RESULT_DATA_SCHEMAS: dict[str, type[ResultData]] = {
    "class_masking": ClassMaskingResultData,
    "size_filter": SizeFilterResultData,
}


def validate_result_data(kind: str, data: dict | ResultData | None) -> dict:
    """``data`` as JSON-ready values, or a ValueError when it does not fit the kind's model."""
    schema = ALGORITHM_RESULT_DATA_SCHEMAS.get(kind)
    if schema is None:
        raise ValueError(f"No result data model is registered for {kind!r}.")
    if isinstance(data, ResultData) and not isinstance(data, schema):
        raise ValueError(f"{type(data).__name__} is not the result data model for {kind!r}.")
    values = data.dict() if isinstance(data, ResultData) else (data or {})
    # Round-trip through JSON so datetimes are stored as ISO strings.
    return pydantic.parse_raw_as(dict, schema.parse_obj(values).json())
