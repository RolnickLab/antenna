"""
Turn a single PipelineProcessingTask into a PipelineTaskResult by running one
of the stub pipelines from processing_services/minimal/api/pipelines.py.

Pipelines and algorithms are imported from `api.*` so that the behavior of the
stub is identical between:
  - v1 POST /process (Antenna sends a PipelineRequest)
  - v2 worker (this file — builds a synthetic one-image PipelineRequest)

Any exception raised during processing is converted to a PipelineResultsError
so the reply_subject ACK still fires downstream.
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any

from api.api import pipeline_choices  # type: ignore[import-not-found]
from api.schemas import SourceImage  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


def process_task(task: dict[str, Any], pipeline_slug: str) -> dict[str, Any]:
    """
    Run the stub pipeline against a single image task.

    Returns a dict shaped like PipelineTaskResult — the worker will POST a list
    of these back to Antenna.
    """
    reply_subject = task.get("reply_subject")
    image_id = task.get("image_id")
    image_url = task.get("image_url")

    try:
        PipelineCls = pipeline_choices[pipeline_slug]
    except KeyError:
        return _error_result(reply_subject, image_id, f"Unknown pipeline slug '{pipeline_slug}'")

    try:
        source_image = SourceImage(id=str(image_id), url=str(image_url))
        source_image.open(raise_exception=True)
    except Exception as e:
        return _error_result(reply_subject, image_id, f"Failed to open image: {e}")

    start = time.time()
    try:
        pipeline = PipelineCls(source_images=[source_image], existing_detections=[])
        detections = pipeline.run()
    except Exception as e:
        logger.exception("Pipeline run failed for task %s", task.get("id"))
        return _error_result(reply_subject, image_id, f"Pipeline run failed: {e}")
    elapsed = time.time() - start

    source_image_response = {
        "id": source_image.id,
        "url": source_image.url,
        "width": source_image.width,
        "height": source_image.height,
    }

    result = {
        "pipeline": pipeline_slug,
        "total_time": elapsed,
        "source_images": [source_image_response],
        "detections": [d.model_dump(mode="json") for d in detections],
    }

    return {
        "reply_subject": reply_subject,
        "result": result,
    }


def _error_result(reply_subject: str | None, image_id: Any, msg: str) -> dict[str, Any]:
    logger.warning("Task error (image_id=%s): %s", image_id, msg)
    return {
        "reply_subject": reply_subject,
        "result": {
            "error": msg,
            "image_id": str(image_id) if image_id is not None else None,
            "_timestamp": datetime.datetime.now().isoformat(),
        },
    }
