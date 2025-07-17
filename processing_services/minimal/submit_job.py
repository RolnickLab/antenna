#!/usr/bin/env python3
"""
Script to submit image processing jobs to the Celery queue.
"""

import argparse
import json
import os
import sys
from typing import Optional

from api.schemas import PipelineRequest, SourceImageRequest
from celery import Celery


def create_celery_app() -> Celery:
    """Create and configure Celery app for job submission."""
    return Celery(
        "image_processing",
        broker=os.getenv("CELERY_BROKER_URL", "amqp://guest@localhost:5672//"),
    )


def submit_pipeline_job(
    pipeline: str, image_urls: list[str], config: dict = None, callback_url: str | None = None
) -> str:
    """
    Submit a pipeline job to the queue.

    Args:
        pipeline: Pipeline type ('random' or 'constant')
        image_urls: List of image URLs to process
        config: Optional configuration dict
        callback_url: Optional URL to POST results to

    Returns:
        Task ID
    """
    if config is None:
        config = {}

    # Create source images
    source_images = [SourceImageRequest(id=f"img_{i}", url=url) for i, url in enumerate(image_urls)]

    # Create pipeline request
    request = PipelineRequest(pipeline=pipeline, source_images=source_images, config=config)

    # Submit to Celery
    app = create_celery_app()
    task = app.send_task("api.tasks.process_pipeline", args=[request.dict(), callback_url])

    return task.id


def main():
    """Command line interface for job submission."""
    parser = argparse.ArgumentParser(description="Submit image processing jobs to Celery queue")
    parser.add_argument("--pipeline", choices=["random", "constant"], default="random", help="Pipeline type to use")
    parser.add_argument(
        "--image-url", action="append", required=True, help="Image URL to process (can be specified multiple times)"
    )
    parser.add_argument("--callback-url", help="Optional callback URL for results")
    parser.add_argument("--config", help="JSON configuration string")
    parser.add_argument("--broker-url", help="Celery broker URL", default="amqp://guest@localhost:5672//")

    args = parser.parse_args()

    # Set broker URL
    os.environ["CELERY_BROKER_URL"] = args.broker_url

    # Parse config
    config = {}
    if args.config:
        try:
            config = json.loads(args.config)
        except json.JSONDecodeError as e:
            print(f"Error parsing config JSON: {e}")
            sys.exit(1)

    # Submit job
    try:
        task_id = submit_pipeline_job(
            pipeline=args.pipeline, image_urls=args.image_url, config=config, callback_url=args.callback_url
        )
        print(f"Job submitted successfully!")
        print(f"Task ID: {task_id}")
        print(f"Pipeline: {args.pipeline}")
        print(f"Images: {len(args.image_url)}")
        if args.callback_url:
            print(f"Callback URL: {args.callback_url}")

    except Exception as e:
        print(f"Error submitting job: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
