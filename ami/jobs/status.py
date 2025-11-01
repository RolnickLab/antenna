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


def _mark_as_failed(job, error_message: str, now: datetime.datetime) -> bool:
    """
    Mark the job as failed.

    Args:
        job: The Job instance
        error_message: The error message to log
        now: The current datetime to use for finished_at

    Returns:
        True if status changed, False if already failed
    """
    from ami.jobs.models import JobState

    if job.status == JobState.FAILURE:
        return False  # No change

    job.logger.error(error_message)
    job.update_status(JobState.FAILURE, save=False)
    job.finished_at = now
    return True


def _check_if_resurrected(job, now: datetime.datetime) -> bool:
    """
    Check if a failed job has been resurrected (Celery task is now running/completed).

    Args:
        job: The Job instance
        now: Current datetime

    Returns:
        True if job was resurrected (status changed), False otherwise
    """
    from ami.jobs.models import JobState

    if job.status != JobState.FAILURE or not job.task_id:
        return False

    try:
        task = AsyncResult(job.task_id)
        celery_status = task.status

        # If the task is now running or succeeded, resurrect the job
        if celery_status in [JobState.STARTED, JobState.SUCCESS]:
            job.logger.warning(
                f"Job was marked FAILURE but task is {celery_status}. Resurrecting job to match task state."
            )
            job.update_status(celery_status, save=False)
            job.finished_at = None if celery_status == JobState.STARTED else job.finished_at
            return True

    except Exception as e:
        job.logger.debug(f"Could not check resurrection status: {e}")

    return False


def _check_missing_task_id(job, now: datetime.datetime) -> bool:
    """
    Check if job was scheduled but never got a task_id.

    Args:
        job: The Job instance
        now: Current datetime

    Returns:
        True if status changed, False otherwise
    """
    from ami.jobs.models import JobState

    if job.task_id or not job.scheduled_at or job.status != JobState.PENDING:
        return False

    time_since_scheduled = (now - job.scheduled_at).total_seconds()
    if time_since_scheduled > job.NO_TASK_ID_TIMEOUT_SECONDS:
        return _mark_as_failed(
            job,
            f"Job scheduled {time_since_scheduled:.0f}s ago but never got a task_id. Marking as FAILURE.",
            now,
        )
    return False


def _check_disappeared_task(job, celery_status: str | None, now: datetime.datetime) -> bool:
    """
    Check if task has disappeared from Celery backend.

    Args:
        job: The Job instance
        celery_status: The task status (may be None)
        now: Current datetime

    Returns:
        True if task disappeared and job was marked failed, False otherwise
    """
    from ami.jobs.models import JobState

    # Detect disappeared task: None status OR PENDING when job isn't actually pending
    is_disappeared = celery_status is None or (
        celery_status == "PENDING" and job.status not in [JobState.CREATED, JobState.PENDING]
    )

    if not is_disappeared:
        return False

    job.logger.warning(f"Task {job.task_id} not found in Celery backend (current job status: {job.status})")

    # If task disappeared shortly after starting, note it might be a worker crash
    if job.status in JobState.running_states() and job.started_at:
        time_since_start = (now - job.started_at).total_seconds()
        if time_since_start < job.DISAPPEARED_TASK_RETRY_THRESHOLD_SECONDS:
            job.logger.info(
                f"Task {job.task_id} disappeared shortly after starting "
                f"(started {time_since_start:.0f}s ago). This may indicate a worker crash."
            )

    # Mark as failed
    return _mark_as_failed(
        job,
        f"Task {job.task_id} disappeared from Celery. Marking as FAILURE.",
        now,
    )


def _check_status_mismatch(job, celery_status: str, now: datetime.datetime) -> bool:
    """
    Check if job status doesn't match Celery task status and reconcile.

    Args:
        job: The Job instance
        celery_status: The status reported by Celery
        now: Current datetime

    Returns:
        True if status changed, False otherwise
    """
    from ami.jobs.models import JobState

    if celery_status == job.status:
        return False

    job.logger.warning(
        f"Job status '{job.status}' doesn't match Celery task status '{celery_status}'. " f"Updating to match Celery."
    )

    old_status = job.status
    job.update_status(celery_status, save=False)

    # If Celery says it's in a final state but we thought it was running
    if celery_status in JobState.final_states() and old_status in JobState.running_states():
        job.finished_at = now
        if celery_status in JobState.failed_states():
            job.logger.error(f"Task failed in Celery")

    return True


def _check_if_stale(job, task: AsyncResult | None, now: datetime.datetime) -> bool:
    """
    Check if job has been running for too long and should be marked as stale.

    Args:
        job: The Job instance
        task: The Celery AsyncResult (may be None if task query failed)
        now: Current datetime

    Returns:
        True if status changed, False otherwise
    """
    from ami.jobs.models import JobState

    if job.status not in JobState.running_states() or not job.started_at:
        return False

    time_since_start = (now - job.started_at).total_seconds()
    if time_since_start <= job.MAX_JOB_RUNTIME_SECONDS:
        return False

    # Job is stale - mark as failed
    max_runtime_hours = job.MAX_JOB_RUNTIME_SECONDS / 3600
    _mark_as_failed(
        job,
        f"Job exceeded maximum runtime of {max_runtime_hours:.0f} hours "
        f"(running for {time_since_start:.0f}s). Marking as FAILURE.",
        now,
    )

    # Try to revoke the task if available
    if task:
        try:
            task.revoke(terminate=True)
            job.logger.info(f"Revoked stale task {job.task_id}")
        except Exception as e:
            job.logger.error(f"Failed to revoke stale task {job.task_id}: {e}")

    return True


def _check_stuck_pending(job, celery_status: str, now: datetime.datetime) -> bool:
    """
    Check if task is stuck in PENDING state for too long.

    Args:
        job: The Job instance
        celery_status: The status reported by Celery
        now: Current datetime

    Returns:
        True if status changed, False otherwise
    """
    from ami.jobs.models import JobState

    if celery_status != JobState.PENDING or not job.scheduled_at:
        return False

    time_since_scheduled = (now - job.scheduled_at).total_seconds()

    # Check if workers are available (using cached check to avoid excessive queries)
    current_minute = int(time.time() / 60)
    workers_available, worker_count = check_celery_workers_available_cached(current_minute)

    # Determine timeout based on worker availability
    timeout = job.STUCK_PENDING_TIMEOUT_SECONDS if workers_available else job.STUCK_PENDING_NO_WORKERS_TIMEOUT_SECONDS

    # Log periodic waiting messages (approximately every 5 minutes)
    if time_since_scheduled > job.PENDING_LOG_INTERVAL_SECONDS:
        # Calculate how many intervals have passed
        intervals_passed = int(time_since_scheduled / job.PENDING_LOG_INTERVAL_SECONDS)
        time_since_last_interval = time_since_scheduled - (intervals_passed * job.PENDING_LOG_INTERVAL_SECONDS)

        # Log if we're within the first 60 seconds of a new interval
        if time_since_last_interval < 60:
            if workers_available:
                job.logger.warning(
                    f"Job has been waiting for {time_since_scheduled:.0f}s "
                    f"with {worker_count} worker(s) available. Task may be queued behind other jobs."
                )
            else:
                job.logger.error(
                    f"Job has been waiting for {time_since_scheduled:.0f}s. "
                    f"NO WORKERS RUNNING - task cannot be picked up until workers start."
                )

    # Check if timeout exceeded
    if time_since_scheduled > timeout:
        if workers_available:
            error_message = (
                f"Job has been pending for {time_since_scheduled:.0f}s " f"with workers available. Marking as FAILURE."
            )
        else:
            error_message = (
                f"Job has been pending for {time_since_scheduled:.0f}s "
                f"with no workers detected. Marking as FAILURE."
            )
        return _mark_as_failed(job, error_message, now)

    return False


def _should_skip_check(job, force: bool, now: datetime.datetime) -> bool:
    """Check if we should skip the status check entirely."""
    if force or not job.last_checked_at:
        return False

    time_since_check = now - job.last_checked_at
    return time_since_check < datetime.timedelta(minutes=2)


def _save_job(job, status_changed: bool, save: bool):
    """Save job with appropriate fields based on whether status changed."""
    if not save:
        return

    fields = ["last_checked_at", "status", "progress", "finished_at"] if status_changed else ["last_checked_at"]
    job.save(update_fields=fields, update_progress=False)


def _get_celery_task_status(job) -> tuple[AsyncResult | None, str | None]:
    """Query Celery for task and its status."""
    try:
        task = AsyncResult(job.task_id)
        return task, task.status
    except Exception as e:
        job.logger.warning(f"Could not query task {job.task_id}: {e}")
        return None, None


def check_job_status(job, force: bool = False, save: bool = True) -> bool:
    """
    Check if the job's Celery task still exists and update status accordingly.

    This function handles multiple scenarios in order:
    1. Resurrection - Job marked failed but task is actually running
    2. Missing task_id - Job scheduled but never got a task ID
    3. Stale job - Job running longer than allowed
    4. Disappeared task - Task existed but is now gone from Celery
    5. Stuck pending - Job waiting too long with/without workers

    Args:
        job: The Job instance to check
        force: Skip the recent check time limit and check final states
        save: Save the job if status changes

    Returns:
        bool: True if job status was changed, False otherwise
    """
    from ami.jobs.models import JobState

    now = timezone.now()

    # Skip if checked recently (unless forced)
    if _should_skip_check(job, force, now):
        job.last_checked_at = now
        _save_job(job, status_changed=False, save=save)
        return False

    job.last_checked_at = now

    # Check 0: Resurrection (failed jobs that came back to life)
    if not force and _check_if_resurrected(job, now):
        _save_job(job, status_changed=True, save=save)
        return True

    # Skip final states unless forced
    if not force and job.status in JobState.final_states():
        _save_job(job, status_changed=False, save=save)
        return False

    # Check 1: Missing Task ID
    if _check_missing_task_id(job, now):
        _save_job(job, status_changed=True, save=save)
        return True

    if not job.task_id:
        _save_job(job, status_changed=False, save=save)
        return False

    # Get Celery task and status
    task, celery_status = _get_celery_task_status(job)

    # Check 2: Stale Job
    if _check_if_stale(job, task, now):
        _save_job(job, status_changed=True, save=save)
        return True

    # Check 3: Disappeared Task (only for non-final states)
    if job.status not in JobState.final_states() and _check_disappeared_task(job, celery_status, now):
        _save_job(job, status_changed=True, save=save)
        return True

    # No celery status available - can't check further
    if not celery_status:
        _save_job(job, status_changed=False, save=save)
        return False

    # Skip PENDING status for final states (task just doesn't exist anymore)
    if job.status in JobState.final_states() and celery_status == JobState.PENDING:
        _save_job(job, status_changed=False, save=save)
        return False

    # Check 4: Stuck pending
    if job.status not in JobState.final_states():
        status_changed = _check_stuck_pending(job, celery_status, now)

    _save_job(job, status_changed, save=save)
    return status_changed
