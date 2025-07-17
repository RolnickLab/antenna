"""
Core processing logic for image pipelines.
This module contains the business logic that can be used by both FastAPI and Celery.
"""

import logging
import time
from typing import Dict, Type

from .pipelines import ConstantPipeline, Pipeline, RandomPipeline
from .schemas import (
    AlgorithmConfigResponse,
    PipelineRequest,
    PipelineResultsResponse,
    SourceImage,
    SourceImageResponse,
)

logger = logging.getLogger(__name__)

# Pipeline registry
pipelines: list[type[Pipeline]] = [RandomPipeline, ConstantPipeline]
pipeline_choices: dict[str, type[Pipeline]] = {pipeline.config.slug: pipeline for pipeline in pipelines}
algorithm_choices: dict[str, AlgorithmConfigResponse] = {
    algorithm.key: algorithm for pipeline in pipelines for algorithm in pipeline.config.algorithms
}


def process_pipeline_request(data: PipelineRequest) -> PipelineResultsResponse:
    """
    Core processing logic that can be used by both FastAPI and Celery.

    Args:
        data: PipelineRequest containing pipeline type, source images, and config

    Returns:
        PipelineResultsResponse with processing results

    Raises:
        ValueError: If invalid pipeline choice is provided
        Exception: If pipeline execution fails
    """
    pipeline_slug = data.pipeline

    source_images = [SourceImage(**image.dict()) for image in data.source_images]
    source_image_results = [SourceImageResponse(**image.dict()) for image in data.source_images]

    start_time = time.time()

    try:
        Pipeline = pipeline_choices[pipeline_slug]
    except KeyError:
        raise ValueError(f"Invalid pipeline choice: {pipeline_slug}")

    pipeline = Pipeline(source_images=source_images)
    try:
        results = pipeline.run()
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        raise Exception(f"Pipeline execution failed: {e}")

    end_time = time.time()
    seconds_elapsed = float(end_time - start_time)

    response = PipelineResultsResponse(
        pipeline=pipeline_slug,
        algorithms={algorithm.key: algorithm for algorithm in pipeline.config.algorithms},
        source_images=source_image_results,
        detections=results,
        total_time=seconds_elapsed,
    )
    return response


def get_pipeline_info() -> list[type[Pipeline]]:
    """Get list of available pipelines."""
    return pipelines


def get_algorithm_choices() -> dict[str, AlgorithmConfigResponse]:
    """Get dictionary of available algorithms."""
    return algorithm_choices
