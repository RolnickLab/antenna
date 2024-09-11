import logging

from ami.ml.media import create_detection_images_from_source_image
from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def process_source_images_async(pipeline_choice: str, endpoint_url: str, image_ids: list[int], job_id: int | None):
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


@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def create_detection_images(source_image_ids: list[int], job_id: int | None = None):
    from ami.jobs.models import Job
    from ami.main.models import SourceImage

    task_logger = logger

    if job_id:
        job = Job.objects.get(pk=job_id)
        task_logger = job.logger

    task_logger.info(f"Creating detection images for {len(source_image_ids)} capture(s)")

    for source_image in SourceImage.objects.filter(pk__in=source_image_ids):
        try:
            processed_paths = create_detection_images_from_source_image(source_image)
            task_logger.info(f"Created {len(processed_paths)} detection images for SourceImage #{source_image.pk}")
        except Exception as e:
            task_logger.error(f"Error processing SourceImage {source_image.pk}: {str(e)}")
