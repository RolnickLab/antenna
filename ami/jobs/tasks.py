import logging

from celery.result import AsyncResult
from celery.signals import task_failure, task_postrun, task_prerun

from ami.jobs.task_state import TaskStateManager
from ami.jobs.utils import _run_in_async_loop
from ami.ml.schemas import PipelineResultsResponse
from ami.tasks import default_soft_time_limit, default_time_limit
from ami.utils.nats_queue import TaskQueueManager
from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def run_job(self, job_id: int) -> None:
    from ami.jobs.models import Job

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist as e:
        raise e
        # self.retry(exc=e, countdown=1, max_retries=1)
    else:
        job.logger.info(f"Running job {job}")
        try:
            job.run()
        except Exception as e:
            job.logger.error(f'Job #{job.pk} "{job.name}" failed: {e}')
            raise
        else:
            job.refresh_from_db()
            job.logger.info(f"Finished job {job}")


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    soft_time_limit=300,  # 5 minutes
    time_limit=360,  # 6 minutes
)
def process_pipeline_result(self, job_id: int, result_data: dict, reply_subject: str) -> None:
    """
    Process a single pipeline result asynchronously.

    This task:
    1. Deserializes the pipeline result
    2. Saves it to the database
    3. Updates progress by removing processed image IDs from Redis
    4. Acknowledges the task via NATS

    Args:
        job_id: The job ID
        result_data: Dictionary containing the pipeline result
        reply_subject: NATS reply subject for acknowledgment

    Returns:
        dict with status information
    """
    from ami.jobs.models import Job, JobState  # avoid circular import

    try:
        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Processing pipeline result for job {job_id}, reply_subject: {reply_subject}")

        # Save to database (this is the slow operation)
        if not job.pipeline:
            job.logger.warning(f"Job {job_id} has no pipeline, skipping save_results")
            return

        job.logger.info(f"Successfully saved results for job {job_id}")

        # Deserialize the result
        pipeline_result = PipelineResultsResponse(**result_data)

        # Update progress tracking in Redis
        state_manager = TaskStateManager(job.pk)
        processed_image_ids = {str(img.id) for img in pipeline_result.source_images}
        state_manager.mark_images_processed(processed_image_ids)

        progress_info = state_manager.get_progress()
        progress_percentage = 0.0

        if progress_info is not None:
            # Get updated progress
            progress_percentage = progress_info.percentage

            job.logger.info(
                f"Job {job_id} progress: {progress_info.processed}/{progress_info.total} images processed "
                f"({progress_percentage*100}%), {progress_info.remaining} remaining"
            )
        else:
            job.logger.warning(f"No pending images found in Redis for job {job_id}, setting progress to 100%")
            progress_percentage = 1.0

        job.progress.update_stage(
            "process",
            status=JobState.SUCCESS if progress_percentage >= 1.0 else JobState.STARTED,
            progress=progress_percentage,
        )
        job.save()

        job.pipeline.save_results(results=pipeline_result, job_id=job.pk)
        # Acknowledge the task via NATS
        try:

            async def ack_task():
                async with TaskQueueManager() as manager:
                    return await manager.acknowledge_task(reply_subject)

            ack_success = _run_in_async_loop(ack_task, f"acknowledging job {job.pk} via NATS")

            if ack_success:
                job.logger.info(f"Successfully acknowledged task via NATS: {reply_subject}")
            else:
                job.logger.warning(f"Failed to acknowledge task via NATS: {reply_subject}")
        except Exception as ack_error:
            job.logger.error(f"Error acknowledging task via NATS: {ack_error}")
            # Don't fail the task if ACK fails - data is already saved

        # Update job stage with calculated progress
        job.progress.update_stage(
            "results",
            status=JobState.STARTED if progress_percentage < 1.0 else JobState.SUCCESS,
            progress=progress_percentage,
        )
        job.save()

    except Job.DoesNotExist:
        logger.error(f"Job {job_id} not found")
        raise
    except Exception as e:
        logger.error(f"Failed to process pipeline result for job {job_id}: {e}")
        # Celery will automatically retry based on autoretry_for
        raise


@task_postrun.connect(sender=run_job)
@task_prerun.connect(sender=run_job)
def update_job_status(sender, task_id, task, *args, **kwargs):
    from ami.jobs.models import Job

    job_id = task.request.kwargs["job_id"]
    if job_id is None:
        logger.error(f"Job id is None for task {task_id}")
        return
    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        try:
            job = Job.objects.get(task_id=task_id)
        except Job.DoesNotExist:
            logger.error(f"No job found for task {task_id} or job_id {job_id}")
            return

    task = AsyncResult(task_id)  # I'm not sure if this is reliable
    job.update_status(task.status, save=False)
    job.save()


@task_failure.connect(sender=run_job, retry=False)
def update_job_failure(sender, task_id, exception, *args, **kwargs):
    from ami.jobs.models import Job, JobState

    job = Job.objects.get(task_id=task_id)
    job.update_status(JobState.FAILURE, save=False)

    job.logger.error(f'Job #{job.pk} "{job.name}" failed: {exception}')

    job.save()
