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
