import logging

from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


# @TODO can the timeout be dynamic based on the number of images?
@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def process_and_save_images(pipeline_choice: str, endpoint_url: str, image_ids: list[int], job_id: int | None):
    from ami.jobs.models import Job
    from ami.main.models import SourceImage
    from ami.ml.models.pipeline import process_images, save_results

    job = None
    try:
        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Processing {len(image_ids)} images for job {job}")
    except Job.DoesNotExist as e:
        logger.error(f"Job {job_id} not found: {e}")
        pass

    images = SourceImage.objects.filter(pk__in=image_ids)
    results = process_images(
        pipeline_choice=pipeline_choice,
        endpoint_url=endpoint_url,
        images=images,
        job_id=job_id,
    )

    try:
        save_results(results=results, job_id=job_id)
    except Exception as e:
        logger.error(f"Failed to save results for job {job_id}: {e}")
        raise e
        # self.retry(exc=e, countdown=2)
