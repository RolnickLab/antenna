"""
v2 pull-mode (worker) Pydantic schemas.

Mirror of the corresponding classes in ami/ml/schemas.py. These live in this
package — separate from api/schemas.py — because they're only used by the
async worker, not by the v1 push FastAPI service. The v1 schemas that are
shared by both paths (PipelineResultsResponse, PipelineConfigResponse, etc.)
stay in api/schemas.py and are imported here.

Keep these in sync with Antenna's canonical schemas when they evolve —
field-for-field parity matters for correct JSON round-trips.
"""

from __future__ import annotations

import pydantic
from api.schemas import PipelineConfigResponse, PipelineResultsResponse  # type: ignore[import-not-found]


class PipelineResultsError(pydantic.BaseModel):
    """Error result when pipeline processing fails for a single task."""

    error: str
    image_id: str | None = None


class PipelineProcessingTask(pydantic.BaseModel):
    """A single image task reserved from the async job queue.

    `reply_subject` is the NATS subject Antenna ACKs on when the result comes
    back — the worker must round-trip it verbatim in the matching
    PipelineTaskResult.
    """

    id: str
    image_id: str
    image_url: str
    reply_subject: str | None = None


class TasksResponse(pydantic.BaseModel):
    """Response body of `POST /api/v2/jobs/{id}/tasks/`."""

    tasks: list[PipelineProcessingTask] = []


class PipelineTaskResult(pydantic.BaseModel):
    """Result of processing a single PipelineProcessingTask."""

    reply_subject: str
    result: PipelineResultsResponse | PipelineResultsError


class ProcessingServiceClientInfo(pydantic.BaseModel):
    """Identity metadata sent by a processing service worker.

    A ProcessingService in the DB may have multiple physical workers running
    simultaneously; this lets the server distinguish them. Fields are
    intentionally open — processing services can send any useful key/value
    pairs (hostname, software version, pod name, etc).
    """

    model_config = pydantic.ConfigDict(extra="allow")


class AsyncPipelineRegistrationRequest(pydantic.BaseModel):
    """Body for `POST /api/v2/projects/{id}/pipelines/` from an async processing service."""

    processing_service_name: str
    pipelines: list[PipelineConfigResponse] = []
