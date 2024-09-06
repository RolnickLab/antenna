import logging

from ami.ml.media import get_source_images_with_missing_detections, process_source_image
from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


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


@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def crop_missing_detection_images(batch_size: int = 100, queryset=None):
    source_images = get_source_images_with_missing_detections(queryset, batch_size)

    for source_image in source_images:
        try:
            processed_paths = process_source_image(source_image)
            logger.info(f"Processed {len(processed_paths)} detections for SourceImage {source_image.id}")
        except Exception as e:
            logger.error(f"Error processing SourceImage {source_image.pk}: {str(e)}")

    logger.info(f"Finished processing batch of {len(source_images)} SourceImages with missing detection paths")


def process_all_missing_detections(batch_size: int = 100, queryset=None):
    while get_source_images_with_missing_detections(queryset, 1):
        crop_missing_detection_images.delay(batch_size, queryset)
