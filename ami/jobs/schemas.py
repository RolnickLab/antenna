import enum

import pydantic
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiParameter


class QueuedTaskAcknowledgment(pydantic.BaseModel):
    """Acknowledgment for a single result that was queued for background processing."""

    reply_subject: str
    status: str
    task_id: str


# What each job type takes. The Create Job dialog renders these models' JSON Schema as its form and
# the API validates a new job against them. Fields named in ``JOB_COLUMNS`` (ami/jobs/models.py) are
# also stored on that Job column. Extra ``Field`` keywords are UI hints that pydantic copies into the
# schema: ``ami_widget="entity"`` + ``ami_entity="<api route>"`` renders a picker (and the server
# checks the id belongs to the project), ``ami_widget="hidden"`` keeps a field out of the form, and
# ``ami_advanced=True`` puts it under "More settings". Use ``typing.Literal`` for choices.


def _pipeline():
    return pydantic.Field(..., title=_("Pipeline"), ami_widget="entity", ami_entity="ml/pipelines")


def _capture_set():
    return pydantic.Field(
        ...,
        title=_("Capture set"),
        ami_widget="entity",
        ami_entity="captures/collections",
    )


def _station():
    return pydantic.Field(..., title=_("Station"), ami_widget="entity", ami_entity="deployments")


class MLJobConfig(pydantic.BaseModel):
    pipeline_id: int = _pipeline()
    source_image_collection_id: int | None = pydantic.Field(
        None,
        title=_("Capture set"),
        description=_("The captures to process."),
        ami_widget="entity",
        ami_entity="captures/collections",
    )
    # Set by other entry points (a single capture's "Process now", a station), not by the dialog.
    source_image_single_id: int | None = pydantic.Field(None, ami_widget="hidden", ami_entity="captures")
    deployment_id: int | None = pydantic.Field(None, ami_widget="hidden", ami_entity="deployments")

    @pydantic.root_validator(skip_on_failure=True)
    def _needs_captures(cls, values: dict) -> dict:
        if not any(values.get(f) for f in ("source_image_collection_id", "source_image_single_id", "deployment_id")):
            raise ValueError("Choose a capture set to process.")
        return values

    class Config:
        extra = "forbid"


class CaptureSetJobConfig(pydantic.BaseModel):
    source_image_collection_id: int = _capture_set()

    class Config:
        extra = "forbid"


class StationJobConfig(pydantic.BaseModel):
    deployment_id: int = _station()

    class Config:
        extra = "forbid"


class JobGroup(str, enum.Enum):
    """Where a job is listed in the Create Job picker, by what the user wants to do.

    Declared by each job type and post-processing task as ``group``; the picker shows the groups in
    this order.
    """

    PROCESS_IMAGES = "process_images"  # sends images to a processing service
    REFINE_RESULTS = "refine_results"  # works on results already in Antenna
    ORGANIZE_CAPTURES = "organize_captures"
    MODELS = "models"


JOB_GROUP_LABELS = {
    JobGroup.PROCESS_IMAGES: _("Process images"),
    JobGroup.REFINE_RESULTS: _("Refine results"),
    JobGroup.ORGANIZE_CAPTURES: _("Organize captures"),
    JobGroup.MODELS: _("Models"),
}


class JobGroupDescription(pydantic.BaseModel):
    """A heading in the Create Job picker."""

    key: JobGroup
    label: str


class JobTypeVariantDescription(pydantic.BaseModel):
    """One method a job type can run, such as a post-processing task."""

    key: str
    name: str
    description: str
    group: JobGroup
    config_schema: dict


class JobTypeDescription(pydantic.BaseModel):
    """A job type the Create Job dialog can offer, as served by ``GET /jobs/types/``."""

    key: str
    name: str
    description: str
    group: JobGroup | None  # None when each variant is listed under its own group instead
    allowed: bool  # whether the requesting user may run it in this project
    config_schema: dict | None
    variant_key: str | None  # the params key holding the chosen variant, e.g. "task"
    variants: list[JobTypeVariantDescription]


ids_only_param = OpenApiParameter(
    name="ids_only",
    description="Return only job IDs instead of full objects",
    required=False,
    type=bool,
)

incomplete_only_param = OpenApiParameter(
    name="incomplete_only",
    description="Filter to only incomplete jobs (excludes jobs with final state in 'results' stage)",
    required=False,
    type=bool,
)

logs_limit_param = OpenApiParameter(
    name="logs_limit",
    description=(
        "Max number of JobLog rows to include in the ``logs`` field on the detail response. "
        "Newest-first. Defaults to 1000, capped at 5000. Pagination over older entries will "
        "ship with a dedicated ``/jobs/logs/`` endpoint."
    ),
    required=False,
    type=int,
)
