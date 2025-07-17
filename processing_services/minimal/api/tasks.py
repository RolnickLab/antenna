"""
Celery tasks for image processing pipelines.
"""

import logging
import os
from typing import Dict, Optional

import requests
from celery import Celery

from .processing import process_pipeline_request
from .schemas import PipelineRequest

logger = logging.getLogger(__name__)

# Celery app configuration
app = Celery(
    "image_processing",
    broker=os.getenv("CELERY_BROKER_URL", "amqp://guest@localhost:5672//"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "file:///tmp/celery-results"),
)

# Celery configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@app.task(bind=True)
def process_pipeline(self, request_data: dict, callback_url: str | None = None) -> dict:
    """
    Process images through pipeline via Celery.

    Args:
        request_data: Serialized PipelineRequest data
        callback_url: Optional URL to POST results to

    Returns:
        Serialized PipelineResultsResponse
    """
    try:
        # Convert dict to PipelineRequest
        request = PipelineRequest(**request_data)

        # Process the pipeline
        response = process_pipeline_request(request)

        # Convert response to dict for serialization
        result = response.dict()

        # Optional: POST results to callback URL
        if callback_url:
            try:
                requests.post(callback_url, json=result, timeout=30, headers={"Content-Type": "application/json"})
                logger.info(f"Successfully posted results to callback URL: {callback_url}")
            except Exception as e:
                logger.error(f"Failed to post results to callback URL {callback_url}: {e}")
                # Don't fail the task if callback fails

        return result

    except Exception as exc:
        logger.error(f"Task failed: {exc}")
        # Update task state with error info
        self.update_state(state="FAILURE", meta={"error": str(exc), "traceback": str(exc.__traceback__)})
        raise exc


@app.task
def health_check() -> dict[str, str]:
    """Simple health check task."""
    return {"status": "healthy", "message": "Celery worker is running"}


@app.task(bind=True)
def save_results(self, request_data: dict) -> dict:
    return {}


if __name__ == "__main__":
    app.start()
