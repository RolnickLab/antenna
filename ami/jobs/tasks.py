import datetime
import functools
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from asgiref.sync import async_to_sync
from celery.signals import task_failure, task_postrun, task_prerun
from django.db import transaction

from ami.ml.orchestration.async_job_state import AsyncJobStateManager
from ami.ml.orchestration.nats_queue import TaskQueueManager
from ami.ml.schemas import PipelineResultsError, PipelineResultsResponse
from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

if TYPE_CHECKING:
    from ami.jobs.models import JobState

logger = logging.getLogger(__name__)
# Minimum success rate. Jobs with fewer than this fraction of images
# processed successfully are marked as failed. Also used in MLJob.process_images().
FAILURE_THRESHOLD = 0.5


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
    max_retries=0,  # don't retry since we already have retry logic in the NATS queue
    soft_time_limit=300,  # 5 minutes
    time_limit=360,  # 6 minutes
)
def process_nats_pipeline_result(self, job_id: int, result_data: dict, reply_subject: str) -> None:
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
    """
    from ami.jobs.models import Job, JobState  # avoid circular import

    _, t = log_time()

    # Validate with Pydantic - check for error response first
    error_result = None
    if "error" in result_data:
        error_result = PipelineResultsError(**result_data)
        processed_image_ids = {str(error_result.image_id)} if error_result.image_id else set()
        failed_image_ids = processed_image_ids  # Same as processed for errors
        pipeline_result = None
    else:
        pipeline_result = PipelineResultsResponse(**result_data)
        processed_image_ids = {str(img.id) for img in pipeline_result.source_images}
        failed_image_ids = set()  # No failures for successful results

    state_manager = AsyncJobStateManager(job_id)

    progress_info = state_manager.update_state(
        processed_image_ids, stage="process", request_id=self.request.id, failed_image_ids=failed_image_ids
    )
    if not progress_info:
        logger.warning(
            f"Another task is already processing results for job {job_id}. "
            f"Retrying task {self.request.id} in 5 seconds..."
        )
        raise self.retry(countdown=5, max_retries=10)

    try:
        complete_state = JobState.SUCCESS
        if progress_info.total > 0 and (progress_info.failed / progress_info.total) > FAILURE_THRESHOLD:
            complete_state = JobState.FAILURE
        _update_job_progress(
            job_id,
            "process",
            progress_info.percentage,
            complete_state=complete_state,
            processed=progress_info.processed,
            remaining=progress_info.remaining,
            failed=progress_info.failed,
        )

        _, t = t(f"TIME: Updated job {job_id} progress in PROCESS stage progress to {progress_info.percentage*100}%")
        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Processing pipeline result for job {job_id}, reply_subject: {reply_subject}")
        job.logger.info(
            f" Job {job_id} progress: {progress_info.processed}/{progress_info.total} images processed "
            f"({progress_info.percentage*100}%), {progress_info.remaining} remaining, {progress_info.failed} failed, "
            f"{len(processed_image_ids)} just processed"
        )
        if error_result:
            job.logger.error(
                f"Pipeline returned error for job {job_id}, image {error_result.image_id}: {error_result.error}"
            )
    except Job.DoesNotExist:
        # don't raise and ack so that we don't retry since the job doesn't exists
        logger.error(f"Job {job_id} not found")
        _ack_task_via_nats(reply_subject, logger)
        return

    try:
        # Save to database (this is the slow operation)
        detections_count, classifications_count, captures_count = 0, 0, 0
        if pipeline_result:
            # should never happen since otherwise we could not be processing results here
            assert job.pipeline is not None, "Job pipeline is None"
            job.pipeline.save_results(results=pipeline_result, job_id=job.pk)
            job.logger.info(f"Successfully saved results for job {job_id}")

            _, t = t(
                f"Saved pipeline results to database with {len(pipeline_result.detections)} detections"
                f", percentage: {progress_info.percentage*100}%"
            )
            # Calculate detection and classification counts from this result
            detections_count = len(pipeline_result.detections)
            classifications_count = sum(len(detection.classifications) for detection in pipeline_result.detections)
            captures_count = len(pipeline_result.source_images)

        _ack_task_via_nats(reply_subject, job.logger)
        # Update job stage with calculated progress

        progress_info = state_manager.update_state(
            processed_image_ids,
            stage="results",
            request_id=self.request.id,
        )

        if not progress_info:
            logger.warning(
                f"Another task is already processing results for job {job_id}. "
                f"Retrying task {self.request.id} in 5 seconds..."
            )
            raise self.retry(countdown=5, max_retries=10)

        # update complete state based on latest progress info after saving results
        complete_state = JobState.SUCCESS
        if progress_info.total > 0 and (progress_info.failed / progress_info.total) > FAILURE_THRESHOLD:
            complete_state = JobState.FAILURE

        _update_job_progress(
            job_id,
            "results",
            progress_info.percentage,
            complete_state=complete_state,
            detections=detections_count,
            classifications=classifications_count,
            captures=captures_count,
        )

    except Exception as e:
        job.logger.error(
            f"Failed to process pipeline result for job {job_id}: {e}. NATS will redeliver the task message."
        )


def _ack_task_via_nats(reply_subject: str, job_logger: logging.Logger) -> None:
    try:

        async def ack_task():
            async with TaskQueueManager() as manager:
                return await manager.acknowledge_task(reply_subject)

        ack_success = async_to_sync(ack_task)()

        if ack_success:
            job_logger.info(f"Successfully acknowledged task via NATS: {reply_subject}")
        else:
            job_logger.warning(f"Failed to acknowledge task via NATS: {reply_subject}")
    except Exception as ack_error:
        job_logger.error(f"Error acknowledging task via NATS: {ack_error}")
        # Don't fail the task if ACK fails - data is already saved


def _get_current_counts_from_job_progress(job, stage: str) -> tuple[int, int, int]:
    """
    Get current detections, classifications, and captures counts from job progress.

    Args:
        job: The Job instance
        stage: The stage name to read counts from

    Returns:
        Tuple of (detections, classifications, captures) counts, defaulting to 0 if not found
    """
    try:
        stage_obj = job.progress.get_stage(stage)

        # Initialize defaults
        detections = 0
        classifications = 0
        captures = 0

        # Search through the params list for our count values
        for param in stage_obj.params:
            if param.key == "detections":
                detections = param.value or 0
            elif param.key == "classifications":
                classifications = param.value or 0
            elif param.key == "captures":
                captures = param.value or 0

        return detections, classifications, captures
    except (ValueError, AttributeError):
        # Stage doesn't exist or doesn't have these attributes yet
        return 0, 0, 0


def _update_job_progress(
    job_id: int, stage: str, progress_percentage: float, complete_state: "JobState", **state_params
) -> None:
    from ami.jobs.models import Job, JobState  # avoid circular import

    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job_id)

        # For results stage, accumulate detections/classifications/captures counts
        if stage == "results":
            current_detections, current_classifications, current_captures = _get_current_counts_from_job_progress(
                job, stage
            )

            # Add new counts to existing counts
            new_detections = state_params.get("detections", 0) or 0
            new_classifications = state_params.get("classifications", 0) or 0
            new_captures = state_params.get("captures", 0) or 0

            state_params["detections"] = current_detections + new_detections
            state_params["classifications"] = current_classifications + new_classifications
            state_params["captures"] = current_captures + new_captures

        job.progress.update_stage(
            stage,
            status=complete_state if progress_percentage >= 1.0 else JobState.STARTED,
            progress=progress_percentage,
            **state_params,
        )
        if job.progress.is_complete():
            job.status = complete_state
            job.progress.summary.status = complete_state
            job.finished_at = datetime.datetime.now()  # Use naive datetime in local time
        job.logger.info(f"Updated job {job_id} progress in stage '{stage}' to {progress_percentage*100}%")
        job.save()

    # Clean up async resources for completed jobs that use NATS/Redis
    if job.progress.is_complete():
        job = Job.objects.get(pk=job_id)  # Re-fetch outside transaction
        _cleanup_job_if_needed(job)


def _cleanup_job_if_needed(job) -> None:
    """
    Clean up async resources (NATS/Redis) if this job uses them.

    Only jobs with ASYNC_API dispatch mode use NATS/Redis resources.
    This function is safe to call for any job - it checks if cleanup is needed.

    Args:
        job: The Job instance
    """
    from ami.jobs.models import JobDispatchMode

    if job.dispatch_mode == JobDispatchMode.ASYNC_API:
        # import here to avoid circular imports
        from ami.ml.orchestration.jobs import cleanup_async_job_resources

        cleanup_async_job_resources(job)


@task_prerun.connect(sender=run_job)
def pre_update_job_status(sender, task_id, task, **kwargs):
    # in the prerun signal, set the job status to PENDING
    update_job_status(sender, task_id, task, "PENDING", **kwargs)


@task_postrun.connect(sender=run_job)
def update_job_status(sender, task_id, task, state: str, retval=None, **kwargs):
    from ami.jobs.models import Job, JobState

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

    # Guard only SUCCESS state - let FAILURE, REVOKED, RETRY pass through immediately
    # SUCCESS should only be set when all stages are actually complete
    # This prevents premature SUCCESS when async workers are still processing
    if state == JobState.SUCCESS and not job.progress.is_complete():
        job.logger.info(
            f"Job {job.pk} task completed but stages not finished - " "deferring SUCCESS status to progress handler"
        )
        return

    job.update_status(state)

    # Clean up async resources for revoked jobs
    if state == JobState.REVOKED:
        _cleanup_job_if_needed(job)


@task_failure.connect(sender=run_job, retry=False)
def update_job_failure(sender, task_id, exception, *args, **kwargs):
    from ami.jobs.models import Job, JobState

    job = Job.objects.get(task_id=task_id)
    job.update_status(JobState.FAILURE, save=False)

    job.logger.error(f'Job #{job.pk} "{job.name}" failed: {exception}')

    job.save()

    # Clean up async resources for failed jobs
    _cleanup_job_if_needed(job)


def log_time(start: float = 0, msg: str | None = None) -> tuple[float, Callable]:
    """
    Small helper to measure time between calls.

    Returns: elapsed time since the last call, and a partial function to measure from the current call
    Usage:

    _, tlog = log_time()
    # do something
    _, tlog = tlog("Did something") # will log the time taken by 'something'
    # do something else
    t, tlog = tlog("Did something else") # will log the time taken by 'something else', returned as 't'
    """

    end = time.perf_counter()
    if start == 0:
        dur = 0.0
    else:
        dur = end - start
    if msg and start > 0:
        logger.info(f"{msg}: {dur:.3f}s")
    new_start = time.perf_counter()
    return dur, functools.partial(log_time, new_start)
