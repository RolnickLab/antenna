import logging

from celery.result import AsyncResult
from celery.signals import task_failure, task_postrun, task_prerun

from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def run_job(self, job_id: int) -> None:
    from ami.jobs.models import Job

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist as e:
        self.retry(exc=e, countdown=1, max_retries=1)
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
