import logging

from asgiref.sync import async_to_sync

from ami.jobs.models import Job, JobState
from ami.main.models import SourceImage
from ami.ml.orchestration.async_job_state import AsyncJobStateManager
from ami.ml.orchestration.nats_queue import TaskQueueManager
from ami.ml.schemas import PipelineProcessingTask

logger = logging.getLogger(__name__)


def cleanup_async_job_resources(job: "Job") -> bool:
    """
    Clean up NATS JetStream and Redis resources for a completed job.

    This function cleans up:
    1. Redis state (via TaskStateManager.cleanup):
    2. NATS JetStream resources (via TaskQueueManager.cleanup_job_resources):

    Cleanup failures are logged but don't fail the job - data is already saved.

    Args:
        job: The Job instance
    Returns:
        bool: True if both cleanups succeeded, False otherwise
    """
    redis_success = False
    nats_success = False

    # Cleanup Redis state
    try:
        state_manager = AsyncJobStateManager(job.pk)
        state_manager.cleanup()
        job.logger.info(f"Cleaned up Redis state for job {job.pk}")
        redis_success = True
    except Exception as e:
        job.logger.error(f"Error cleaning up Redis state for job {job.pk}: {e}")

    # Cleanup NATS resources
    async def cleanup():
        manager = TaskQueueManager()
        return await manager.cleanup_job_resources(job.pk)

    try:
        nats_success = async_to_sync(cleanup)()
        if nats_success:
            job.logger.info(f"Cleaned up NATS resources for job {job.pk}")
        else:
            job.logger.warning(f"Failed to clean up NATS resources for job {job.pk}")
    except Exception as e:
        job.logger.error(f"Error cleaning up NATS resources for job {job.pk}: {e}")

    return redis_success and nats_success


def queue_images_to_nats(job: "Job", images: list[SourceImage]):
    """
    Queue all images for a job to a NATS JetStream stream for the job.

    Args:
        job: The Job instance
        images: List of SourceImage instances to queue

    Returns:
        bool: True if all images were successfully queued, False otherwise
    """
    job.logger.info(f"Queuing {len(images)} images to NATS stream for job '{job.pk}'")

    # Prepare all messages outside of async context to avoid Django ORM issues
    tasks: list[tuple[int, PipelineProcessingTask]] = []
    image_ids = []
    skipped_count = 0
    for image in images:
        image_id = str(image.pk)
        image_url = image.url() if hasattr(image, "url") and image.url() else ""
        if not image_url:
            job.logger.warning(f"Image {image.pk} has no URL, skipping queuing to NATS for job '{job.pk}'")
            skipped_count += 1
            continue
        image_ids.append(image_id)
        task = PipelineProcessingTask(
            id=image_id,
            image_id=image_id,
            image_url=image_url,
        )
        tasks.append((image.pk, task))

    # Store all image IDs in Redis for progress tracking
    state_manager = AsyncJobStateManager(job.pk)
    state_manager.initialize_job(image_ids)
    job.logger.info(f"Initialized task state tracking for {len(image_ids)} images")

    async def queue_all_images():
        successful_queues = 0
        failed_queues = 0

        manager = TaskQueueManager()
        for image_pk, task in tasks:
            try:
                logger.info(f"Queueing image {image_pk} to stream for job '{job.pk}': {task.image_url}")
                success = await manager.publish_task(
                    job_id=job.pk,
                    data=task,
                )
            except Exception as e:
                logger.exception(f"Failed to queue image {image_pk} to stream for job '{job.pk}': {e}")
                success = False

            if success:
                successful_queues += 1
            else:
                failed_queues += 1

        return successful_queues, failed_queues

    if tasks:
        successful_queues, failed_queues = async_to_sync(queue_all_images)()
        # Add skipped images to failed count
        failed_queues += skipped_count
    else:
        # If no tasks but there are skipped images, mark as failed
        if skipped_count > 0:
            job.progress.update_stage("process", status=JobState.FAILURE, progress=1.0)
            job.progress.update_stage("results", status=JobState.FAILURE, progress=1.0)
        else:
            job.progress.update_stage("process", status=JobState.SUCCESS, progress=1.0)
            job.progress.update_stage("results", status=JobState.SUCCESS, progress=1.0)
        job.save()
        successful_queues, failed_queues = 0, skipped_count

    # Log results (back in sync context)
    if successful_queues > 0:
        job.logger.info(f"Successfully queued {successful_queues}/{len(images)} images to stream for job '{job.pk}'")

    if failed_queues > 0:
        job.logger.warning(
            f"Failed to queue {failed_queues}/{len(images)} images to stream for job '{job.pk}' (including "
            f"{skipped_count} skipped images)"
        )
        return False

    return True
