import logging

from asgiref.sync import async_to_sync

from ami.jobs.models import Job, JobState
from ami.main.models import SourceImage
from ami.ml.orchestration.async_job_state import AsyncJobStateManager
from ami.ml.orchestration.nats_queue import TaskQueueManager
from ami.ml.schemas import PipelineProcessingTask

logger = logging.getLogger(__name__)


def cleanup_async_job_resources(job_id: int) -> bool:
    """
    Clean up NATS JetStream and Redis resources for a completed job.

    This function cleans up:
    1. Redis state (via TaskStateManager.cleanup):
    2. NATS JetStream resources (via TaskQueueManager.cleanup_job_resources):

    Cleanup failures are logged but don't fail the job - data is already saved.

    Resolves the job (and its per-job logger) internally so callers only need
    to pass the ``job_id`` — matches the pattern used by ``save_results`` in
    ``ami/jobs/tasks.py``. If the ``Job`` row is gone (e.g. the
    ``Job.DoesNotExist`` path in ``_fail_job``), the function falls back to
    the module logger and TaskQueueManager's module-logger path.

    Args:
        job_id: The Job ID (integer primary key).
    Returns:
        bool: True if both cleanups succeeded, False otherwise
    """
    # Resolve the logger up front: job.logger when the Job exists, module
    # logger otherwise. Matches the pattern used by save_results.
    job: Job | None = None
    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        pass
    job_logger: logging.Logger = job.logger if job else logger

    redis_success = False
    nats_success = False

    # Cleanup Redis state
    try:
        state_manager = AsyncJobStateManager(job_id)
        state_manager.cleanup()
        job_logger.info(f"Cleaned up Redis state for job {job_id}")
        redis_success = True
    except Exception as e:
        job_logger.error(f"Error cleaning up Redis state for job {job_id}: {e}")

    # Cleanup NATS resources. Only forward a real per-job logger to
    # TaskQueueManager — passing the module logger would mirror cleanup
    # lifecycle lines into an unrelated logger.
    async def cleanup():
        async with TaskQueueManager(job_logger=job.logger if job else None) as manager:
            return await manager.cleanup_job_resources(job_id)

    try:
        nats_success = async_to_sync(cleanup)()
        if nats_success:
            job_logger.info(f"Cleaned up NATS resources for job {job_id}")
        else:
            job_logger.warning(f"Failed to clean up NATS resources for job {job_id}")
    except Exception as e:
        job_logger.error(f"Error cleaning up NATS resources for job {job_id}: {e}")

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
    pipeline_config = job.pipeline.get_config(project_id=job.project.pk) if job.pipeline else None

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
            config=pipeline_config,
        )
        tasks.append((image.pk, task))

    # Store all image IDs in Redis for progress tracking
    state_manager = AsyncJobStateManager(job.pk)
    state_manager.initialize_job(image_ids)
    job.logger.info(f"Initialized task state tracking for {len(image_ids)} images")

    async def queue_all_images():
        successful_queues = 0
        failed_queues = 0

        # Pass job.logger so stream/consumer setup, per-image debug lines, and
        # publish failures all appear in the UI job log (not just the module
        # logger). All log calls inside this block go through manager.log_async
        # so module + job logger stay in sync with one consistent API — and
        # the sync_to_async bridge for JobLogHandler's ORM save lives in one
        # place instead of being re-implemented at every call site.
        async with TaskQueueManager(job_logger=job.logger) as manager:
            for image_pk, task in tasks:
                try:
                    await manager.log_async(
                        logging.DEBUG,
                        f"Queueing image {image_pk} to stream for job '{job.pk}': {task.image_url}",
                    )
                    success = await manager.publish_task(
                        job_id=job.pk,
                        data=task,
                    )
                except Exception as e:
                    await manager.log_async(
                        logging.ERROR,
                        f"Failed to queue image {image_pk} to stream for job '{job.pk}': {e}",
                        exc_info=True,
                    )
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
