"""
Turn a single PipelineProcessingTask into a PipelineTaskResult by running one
of the stub pipelines from processing_services/minimal/api/pipelines.py.

Pipelines and algorithms are imported from `api.*` so that the behavior of the
stub is identical between:
  - v1 POST /process (Antenna sends a PipelineRequest)
  - v2 worker (this file — builds a synthetic one-image run)

Any exception raised during processing is converted to a PipelineResultsError
so the reply_subject ACK still fires downstream.
"""

from __future__ import annotations

import logging
import os
import time

from api.api import worker_pipelines  # type: ignore[import-not-found]
from api.schemas import (  # type: ignore[import-not-found]
    PipelineRequestConfigParameters,
    PipelineResultsResponse,
    SourceImage,
    SourceImageResponse,
)

from .schemas import PipelineProcessingTask, PipelineResultsError, PipelineTaskResult

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes", "on")


def worker_request_config() -> PipelineRequestConfigParameters:
    """The request config for pull-mode tasks, read from the environment.

    Pull-mode tasks carry no config (see #1422), so the worker reads the same settings the
    AMI Data Companion worker does. Unset variables keep the push-mode defaults.
    """
    return PipelineRequestConfigParameters(
        include_logits=_env_flag("AMI_INCLUDE_LOGITS", True),
        features_for_all_detections=_env_flag("AMI_FEATURES_FOR_ALL_DETECTIONS", False),
        embedding_extractor=os.environ.get("AMI_EMBEDDING_EXTRACTOR"),
    )


def process_task(task: PipelineProcessingTask, pipeline_slug: str) -> PipelineTaskResult:
    """
    Run the stub pipeline against a single image task.
    """
    # The reserve_tasks endpoint always returns a reply_subject for v2 tasks;
    # if we somehow got None, the server's ACK path won't fire — we still
    # return a result so the caller can log it.
    reply_subject = task.reply_subject or ""

    try:
        PipelineCls = {pipeline.config.slug: pipeline for pipeline in worker_pipelines}[pipeline_slug]
    except KeyError:
        return _error_result(reply_subject, task.image_id, f"Unknown pipeline slug '{pipeline_slug}'")

    try:
        source_image = SourceImage(id=task.image_id, url=task.image_url)
        source_image.open(raise_exception=True)
    except Exception as e:
        return _error_result(reply_subject, task.image_id, f"Failed to open image: {e}")

    start = time.time()
    try:
        pipeline = PipelineCls(
            source_images=[source_image], existing_detections=[], request_config=worker_request_config()
        )
        detections = pipeline.run()
    except Exception as e:
        logger.exception("Pipeline run failed for task %s", task.id)
        return _error_result(reply_subject, task.image_id, f"Pipeline run failed: {e}")
    elapsed = time.time() - start

    result = PipelineResultsResponse(
        pipeline=pipeline_slug,  # type: ignore[arg-type]  # already validated via pipeline_choices lookup
        total_time=elapsed,
        source_images=[SourceImageResponse(id=source_image.id, url=source_image.url or "")],
        detections=detections,
    )
    return PipelineTaskResult(reply_subject=reply_subject, result=result)


def _error_result(reply_subject: str, image_id: str, msg: str) -> PipelineTaskResult:
    logger.warning("Task error (image_id=%s): %s", image_id, msg)
    return PipelineTaskResult(
        reply_subject=reply_subject,
        result=PipelineResultsError(error=msg, image_id=image_id),
    )
