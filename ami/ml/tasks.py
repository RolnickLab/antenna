import logging

from ami.ml.media import create_detection_images_from_source_image
from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def process_source_images_async(pipeline_choice: str, endpoint_url: str, image_ids: list[int], job_id: int | None):
    from ami.jobs.models import Job
    from ami.main.models import SourceImage
    from ami.ml.models.pipeline import Pipeline, process_images, save_results

    job = None
    try:
        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Processing {len(image_ids)} images for job {job}")
    except Job.DoesNotExist as e:
        logger.error(f"Job {job_id} not found: {e}")
        pass

    images = SourceImage.objects.filter(pk__in=image_ids)
    pipeline = Pipeline.objects.get(slug=pipeline_choice)

    results = process_images(
        pipeline=pipeline,
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
def create_detection_images(source_image_ids: list[int]):
    from ami.main.models import SourceImage

    logger.debug(f"Creating detection images for {len(source_image_ids)} capture(s)")

    for source_image in SourceImage.objects.filter(pk__in=source_image_ids):
        try:
            processed_paths = create_detection_images_from_source_image(source_image)
            logger.debug(f"Created {len(processed_paths)} detection images for SourceImage #{source_image.pk}")
        except Exception as e:
            logger.error(f"Error creating detection images for SourceImage {source_image.pk}: {str(e)}")


@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def remove_duplicate_classifications(project_id: int | None = None, dry_run: bool = False) -> int:
    """
    Remove duplicate classifications from the database.

    A duplicate classification is one where the same detection, taxon, algorithm, score, softmax_output and raw_output
    have been classified more than once. This can happen if the same detection is classified multiple times by the same
    algorithm with the same result.

    This method will keep the oldest classification and delete the rest.
    """
    from ami.main.models import Classification

    # Find the oldest classification for each unique combination
    duplicates_to_delete = Classification.objects.find_duplicates(project_id=project_id)  # type: ignore
    num = duplicates_to_delete.count()

    logger.info(f"Found {duplicates_to_delete.count()} duplicate classifications to delete")
    if dry_run:
        logger.info(f"Would delete {num} duplicate classifications")
    else:
        num_deleted = duplicates_to_delete.delete()
        logger.info(f"Deleted {num_deleted} duplicate classifications")

    return num_deleted
