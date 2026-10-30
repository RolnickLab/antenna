"""
What a retraining job is asked to do: which head, which species list, and which data it learns from.

Checked when the job is created (``TrainClassifierJob.config_schema``), so a bad setting is a 400
on the form rather than a failed run. The fitting settings (``test_fraction``, ``epochs``, ...)
are not declared here: they pass through and are checked by ``AlgorithmTrainingConfig``, which
also owns their defaults, so the two cannot drift apart.
"""

import pydantic

from ami.base.model_references import model_reference
from ami.ml.schemas import AlgorithmTrainingConfig


class TrainClassifierJobConfig(pydantic.BaseModel):
    algorithm_key: str = pydantic.Field(..., min_length=1, title="Algorithm")
    taxa_list_id: int | None = model_reference(
        "taxa_list",
        None,
        title="Species list",
        description="The species the head covers. Defaults to the project's default taxa list.",
    )

    # Data the head learns from. Each source is optional; at least one must be on.
    use_project_occurrences: bool = pydantic.Field(
        True, title="This project's verified occurrences", description="Every verified occurrence, or one set."
    )
    occurrence_set_id: int | None = pydantic.Field(
        None, title="Occurrence set", description="Learn from this set only, instead of every verified occurrence."
    )
    use_offline_inat: bool = pydantic.Field(
        False,
        title="Offline iNaturalist data",
        description="Images the processing service already holds, filtered to the species list.",
    )

    class Config:
        # Fitting overrides pass through to AlgorithmTrainingConfig; see the module docstring.
        extra = "allow"

    @pydantic.root_validator(skip_on_failure=True)
    def _sources_make_sense(cls, values: dict) -> dict:
        if not (values.get("use_project_occurrences") or values.get("use_offline_inat")):
            raise ValueError("Choose at least one source of training data.")
        if values.get("occurrence_set_id") is not None and not values.get("use_project_occurrences"):
            raise ValueError("An occurrence set narrows this project's occurrences, which are switched off.")
        if values.get("use_offline_inat"):
            # Not offered until the processing service can train from it.
            raise ValueError("Offline iNaturalist data is not available for training yet.")
        return values

    @pydantic.root_validator(skip_on_failure=True)
    def _fitting_overrides_in_range(cls, values: dict) -> dict:
        # Bounds only: the algorithm's own defaults are applied when the job runs (config_for).
        try:
            AlgorithmTrainingConfig.for_run(AlgorithmTrainingConfig(), values)
        except pydantic.ValidationError as e:
            raise ValueError("; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()))
        return values
