"""
Job status checking utilities for monitoring and updating job states.

This module provides functions to check if Celery tasks still exist and update
job statuses accordingly when tasks disappear, get stuck, or exceed timeouts.
"""
import datetime
import functools
import logging
import time

from celery.result import AsyncResult
from django.utils import timezone

from config import celery_app

logger = logging.getLogger(__name__)


def check_celery_workers_available() -> tuple[bool, int]:
    """
    Check if any Celery workers are currently running.

    Returns:
        tuple: (workers_available: bool, worker_count: int)
    """
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()

        if active_workers is None:
            return False, 0

        worker_count = len(active_workers)
        return worker_count > 0, worker_count
    except Exception as e:
        logger.warning(f"Failed to check for Celery workers: {e}")
        return True, 0  # Fail open - assume workers might be available


@functools.lru_cache(maxsize=1)
def check_celery_workers_available_cached(timestamp: int) -> tuple[bool, int]:
    """
    Cached version of worker availability check.

    Cache key is current minute, so results are cached for ~1 minute.

    Args:
        timestamp: Current minute as int(time.time() / 60)

    Returns:
        tuple: (workers_available: bool, worker_count: int)
    """
    return check_celery_workers_available()


def check_job_status(job, force: bool = False, save: bool = True) -> bool:
    """
    Check if the job's Celery task still exists and update status accordingly.

    This function handles multiple scenarios:
    1. Missing task_id - Job scheduled but never got a task ID
    2. Disappeared task - Task existed but is now gone from Celery
    3. Stuck pending - Job waiting too long with no workers
    4. Max runtime exceeded - Job running longer than allowed
    5. Resurrection - Job marked failed but task is actually running

    Args:
        job: The Job instance to check
        force: Skip the recent check time limit
        save: Save the job if status changes

    Returns:
        bool: True if job status was changed, False otherwise
    """
    from ami.jobs.models import JobState

    now = timezone.now()
    status_changed = False

    # Skip if checked recently (unless forced)
    if not force and job.last_checked_at:
        time_since_check = now - job.last_checked_at
        if time_since_check < datetime.timedelta(minutes=2):
            # Still update last_checked_at even though we're skipping
            if save:
                job.last_checked_at = now
                job.save(update_fields=["last_checked_at"], update_progress=False)
            return False

    # Update last_checked_at for this check
    if save:
        job.last_checked_at = now

    # Skip if job is already in a final state
    if job.status in JobState.final_states():
        if save:
            job.save(update_fields=["last_checked_at"], update_progress=False)
        return False

    # Scenario 4: Max Runtime Exceeded (check this first - doesn't require Celery query)
    if job.status == JobState.STARTED and job.started_at:
        runtime = (now - job.started_at).total_seconds()

        if runtime > job.MAX_JOB_RUNTIME_SECONDS:
            job.logger.error(
                f"Job exceeded maximum runtime of {job.MAX_JOB_RUNTIME_SECONDS}s "
                f"(running for {runtime:.0f}s). Marking as FAILURE."
            )
            job.update_status(JobState.FAILURE, save=False)
            status_changed = True
            if save:
                job.save(update_progress=False)
            return status_changed

    # Scenario 1: Missing Task ID
    if not job.task_id:
        if job.status == JobState.PENDING and job.scheduled_at:
            time_waiting = (now - job.scheduled_at).total_seconds()
            if time_waiting > job.NO_TASK_ID_TIMEOUT_SECONDS:
                job.logger.error(
                    f"Job scheduled {time_waiting:.0f}s ago but never got a task_id. " f"Marking as FAILURE."
                )
                job.update_status(JobState.FAILURE, save=False)
                status_changed = True
                if save:
                    job.save(update_progress=False)
                return status_changed

    # Scenario 2-5: Has task_id
    if job.task_id:
        try:
            task = AsyncResult(job.task_id)
            celery_status = task.status

            # Scenario 2: Disappeared Task
            # If Celery says PENDING but job was STARTED, task disappeared
            if celery_status == "PENDING" and job.status == JobState.STARTED:
                if job.started_at:
                    time_since_start = (now - job.started_at).total_seconds()
                    if time_since_start > job.DISAPPEARED_TASK_RETRY_THRESHOLD_SECONDS:
                        job.logger.error(
                            f"Task {job.task_id} disappeared from Celery "
                            f"(started {time_since_start:.0f}s ago). Marking as FAILURE."
                        )
                        job.update_status(JobState.FAILURE, save=False)
                        status_changed = True

            # Scenario 5: Resurrection
            # Job marked as FAILURE but task is actually running or succeeded
            elif job.status == JobState.FAILURE and celery_status in ["STARTED", "SUCCESS"]:
                job.logger.warning(
                    f"Job was marked FAILURE but task is {celery_status}. " f"Resurrecting job to match task state."
                )
                job.update_status(celery_status, save=False)
                status_changed = True

        except Exception as e:
            job.logger.warning(f"Could not check task {job.task_id} status: {e}")

    # Scenario 3: Stuck Pending (No Workers)
    if job.status == JobState.PENDING and job.scheduled_at:
        time_pending = (now - job.scheduled_at).total_seconds()

        if time_pending > job.STUCK_PENDING_TIMEOUT_SECONDS:
            workers_available, worker_count = check_celery_workers_available_cached(
                int(time.time() / 60)  # Cache for 1 minute
            )

            if not workers_available:
                job.logger.warning(
                    f"Job stuck in PENDING for {time_pending:.0f}s "
                    f"but no workers available (worker_count={worker_count}). "
                    f"Not marking as failed yet - may just be queued."
                )
            # Don't mark as failed - might just be queued behind other jobs

    # Save if status changed or if we need to update last_checked_at
    if save:
        job.save(update_progress=False)

    return status_changed
