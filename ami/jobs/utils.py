"""Utility functions for job management and testing."""

import logging

from ami.jobs.models import Job, MLJob
from ami.main.models import Project, SourceImage
from ami.ml.models import Pipeline

logger = logging.getLogger(__name__)


def submit_single_image_job(
    image_id: int,
    pipeline_id: int,
    project_id: int | None = None,
    job_name: str | None = None,
) -> Job:
    """
    Submit a job to process a single image through a pipeline.

    This is useful for testing, debugging, or reprocessing individual images.

    Args:
        image_id: The SourceImage ID to process
        pipeline_id: The Pipeline ID to use for processing
        project_id: Optional project ID (will be inferred from image if not provided)
        job_name: Optional custom job name (will be auto-generated if not provided)

    Returns:
        The created Job instance

    Raises:
        SourceImage.DoesNotExist: If the image doesn't exist
        Pipeline.DoesNotExist: If the pipeline doesn't exist
    """
    # Fetch the image and validate it exists
    try:
        image = SourceImage.objects.select_related("deployment__project").get(pk=image_id)
    except SourceImage.DoesNotExist:
        logger.error(f"SourceImage with id {image_id} does not exist")
        raise

    # Fetch the pipeline and validate it exists
    try:
        pipeline = Pipeline.objects.get(pk=pipeline_id)
    except Pipeline.DoesNotExist:
        logger.error(f"Pipeline with id {pipeline_id} does not exist")
        raise

    # Infer project from image if not provided
    if project_id is None:
        project = image.deployment.project
    else:
        project = Project.objects.get(pk=project_id)

    # Generate job name if not provided
    if job_name is None:
        job_name = f"Single image {image_id} - {pipeline.name}"

    # Create the job
    job = Job.objects.create(
        name=job_name,
        project=project,
        pipeline=pipeline,
        job_type_key=MLJob.key,
        source_image_single=image,
    )

    logger.info(
        f"Created job {job.pk} for single image {image_id} " f"with pipeline {pipeline.name} (id: {pipeline_id})"
    )

    # Enqueue the job (starts the Celery task)
    job.enqueue()

    logger.info(f"Job {job.pk} enqueued with task_id: {job.task_id}")

    return job
