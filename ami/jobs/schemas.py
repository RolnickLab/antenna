import pydantic
from drf_spectacular.utils import OpenApiParameter


class QueuedTaskAcknowledgment(pydantic.BaseModel):
    """Acknowledgment for a single result that was queued for background processing."""

    reply_subject: str
    status: str
    task_id: str


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
