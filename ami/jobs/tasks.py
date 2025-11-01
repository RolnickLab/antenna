import datetime
import logging

from celery.result import AsyncResult
from celery.signals import task_failure, task_postrun, task_prerun
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.utils import timezone

from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)
task_logger = get_task_logger(__name__)


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


@celery_app.task(soft_time_limit=300, time_limit=360)
def check_incomplete_jobs() -> dict[str, int | str]:
    """
    Periodic task to check status of all incomplete jobs.

    This task identifies jobs stuck in non-final states and verifies their
    Celery tasks still exist. If tasks have disappeared or jobs have exceeded
    timeouts, their status is updated accordingly.

    Uses cache-based locking to prevent duplicate execution.

    Returns:
        dict: Summary with counts of jobs checked, updated, and any errors
    """
    from ami.jobs.models import Job, JobState

    # Configuration
    LOCK_TIMEOUT_SECONDS = 300  # 5 minutes
    MAX_JOBS_PER_RUN = 100
    MIN_CHECK_INTERVAL_MINUTES = 2

    # Use cache-based locking to prevent duplicates
    lock_id = "check_incomplete_jobs_lock"

    if not cache.add(lock_id, "locked", LOCK_TIMEOUT_SECONDS):
        task_logger.info("check_incomplete_jobs already running, skipping")
        return {"status": "skipped", "reason": "already_running"}

    try:
        task_logger.info("Starting check_incomplete_jobs task")

        # Get all incomplete jobs
        incomplete_jobs = Job.objects.filter(status__in=JobState.running_states()).order_by("scheduled_at")

        total_jobs = incomplete_jobs.count()
        task_logger.info(f"Found {total_jobs} incomplete jobs")

        if total_jobs == 0:
            return {"status": "success", "checked": 0, "updated": 0}

        # Limit to avoid overwhelming the system
        if total_jobs > MAX_JOBS_PER_RUN:
            task_logger.warning(f"Limiting to {MAX_JOBS_PER_RUN} jobs")
            incomplete_jobs = incomplete_jobs[:MAX_JOBS_PER_RUN]

        # Filter to jobs not checked recently
        now = timezone.now()
        min_check_interval = datetime.timedelta(minutes=MIN_CHECK_INTERVAL_MINUTES)

        jobs_to_check = []
        for job in incomplete_jobs:
            if job.last_checked_at is None:
                jobs_to_check.append(job)
            elif (now - job.last_checked_at) >= min_check_interval:
                jobs_to_check.append(job)

        task_logger.info(f"Checking {len(jobs_to_check)} jobs needing verification")

        checked_count = 0
        updated_count = 0
        error_count = 0

        for job in jobs_to_check:
            try:
                status_changed = job.check_status(force=False, save=True)
                checked_count += 1
                if status_changed:
                    updated_count += 1
                    task_logger.info(f"Updated job {job.pk} status to {job.status}")
            except Exception as e:
                error_count += 1
                task_logger.error(f"Error checking job {job.pk}: {e}", exc_info=True)

        result = {
            "status": "success",
            "total_incomplete": total_jobs,
            "checked": checked_count,
            "updated": updated_count,
            "errors": error_count,
        }
        task_logger.info(f"Completed check_incomplete_jobs: {result}")
        return result

    finally:
        # Always release the lock
        cache.delete(lock_id)
