import logging

from celery.result import AsyncResult
from celery.signals import task_failure, task_postrun, task_prerun
from celery.utils.log import get_task_logger
from django.core.cache import cache

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
    job.save(update_fields=["status", "progress"])


@task_failure.connect(sender=run_job, retry=False)
def update_job_failure(sender, task_id, exception, *args, **kwargs):
    from ami.jobs.models import Job, JobState

    job = Job.objects.get(task_id=task_id)
    job.update_status(JobState.FAILURE, save=False)

    job.logger.error(f'Job #{job.pk} "{job.name}" failed: {exception}')

    job.save(update_fields=["status", "progress"])


@celery_app.task(soft_time_limit=300, time_limit=360)
def check_unfinished_jobs():
    """
    Periodic task to check the status of all unfinished jobs.

    This task prevents duplicate execution using cache-based locking and
    checks jobs that haven't been verified recently to ensure their Celery
    tasks are still active and their statuses are accurate.
    """
    import datetime

    from ami.jobs.models import Job, JobState

    # Configuration thresholds (TODO: make these configurable via settings)
    LOCK_TIMEOUT_SECONDS = 300  # 5 minutes - how long the lock is held
    MAX_JOBS_PER_RUN = 100  # Maximum number of jobs to check in one run
    MIN_CHECK_INTERVAL_MINUTES = 2  # Minimum time between checks for the same job

    # Use cache-based locking to prevent duplicate checks
    lock_id = "check_unfinished_jobs_lock"

    # Try to acquire lock
    if not cache.add(lock_id, "locked", LOCK_TIMEOUT_SECONDS):
        task_logger.info("check_unfinished_jobs is already running, skipping this execution")
        return {"status": "skipped", "reason": "already_running"}

    try:
        task_logger.info("Starting check_unfinished_jobs task")

        # Get all jobs that are not in final states
        unfinished_jobs = Job.objects.filter(status__in=JobState.running_states()).order_by("scheduled_at")

        total_jobs = unfinished_jobs.count()
        task_logger.info(f"Found {total_jobs} unfinished jobs to check")

        if total_jobs == 0:
            return {"status": "success", "checked": 0, "updated": 0}

        # Avoid checking too many jobs at once
        if total_jobs > MAX_JOBS_PER_RUN:
            task_logger.warning(f"Limiting check to {MAX_JOBS_PER_RUN} jobs (out of {total_jobs})")
            unfinished_jobs = unfinished_jobs[:MAX_JOBS_PER_RUN]

        # Only check jobs that haven't been checked recently
        now = datetime.datetime.now()
        min_check_interval = datetime.timedelta(minutes=MIN_CHECK_INTERVAL_MINUTES)

        jobs_to_check = []
        for job in unfinished_jobs:
            if job.last_checked_at is None:
                jobs_to_check.append(job)
            else:
                time_since_check = now - job.last_checked_at
                if time_since_check >= min_check_interval:
                    jobs_to_check.append(job)

        task_logger.info(f"Checking {len(jobs_to_check)} jobs that need status verification")

        checked_count = 0
        updated_count = 0
        error_count = 0

        for job in jobs_to_check:
            try:
                task_logger.debug(f"Checking job {job.pk}: {job.name} (status: {job.status})")
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
            "total_unfinished": total_jobs,
            "checked": checked_count,
            "updated": updated_count,
            "errors": error_count,
        }
        task_logger.info(f"Completed check_unfinished_jobs: {result}")
        return result

    finally:
        # Always release the lock
        cache.delete(lock_id)
