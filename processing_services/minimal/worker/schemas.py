"""
Local mirrors of the v2 Pydantic schemas.

The canonical definitions live in `ami/ml/schemas.py` inside Antenna. We mirror
them here rather than import because this container does not install the ami
package. When Antenna evolves the schemas, keep these in sync — field-for-field
parity matters for correct JSON round-trips.

Kept intentionally small: only the fields this stub reads or writes. Extra
fields returned by Antenna are tolerated via Pydantic's default `extra=ignore`.
"""

from __future__ import annotations

import pydantic


class PipelineProcessingTask(pydantic.BaseModel):
    """Mirror of ami.ml.schemas.PipelineProcessingTask.

    A task representing a single image to be processed in an async pipeline.
    `reply_subject` is the NATS subject that Antenna ACKs on when the result
    comes back — we just round-trip it.
    """

    id: str
    image_id: str
    image_url: str
    reply_subject: str | None = None


class TasksResponse(pydantic.BaseModel):
    """Response body of POST /jobs/{id}/tasks/"""

    tasks: list[PipelineProcessingTask] = []
