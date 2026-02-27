import logging
import time

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
    reprocess_all_images = False
    if job_id is not None:
        try:
            job = Job.objects.get(pk=job_id)
            reprocess_all_images = job.project.feature_flags.reprocess_all_images
            job.logger.info(
                f"Processing {len(image_ids)} images for job {job} (reprocess_all_images={reprocess_all_images})"
            )
        except Job.DoesNotExist as e:
            logger.error(f"Job {job_id} not found: {e}")

    else:
        logger.info(
            f"Processing {len(image_ids)} images for job_id=None (reprocess_all_images={reprocess_all_images})"
        )

    images = SourceImage.objects.filter(pk__in=image_ids)
    pipeline = Pipeline.objects.get(slug=pipeline_choice)

    results = process_images(
        pipeline=pipeline,
        endpoint_url=endpoint_url,
        images=images,
        job_id=job_id,
        reprocess_all_images=reprocess_all_images,
    )

    try:
        save_results(results=results, job_id=job_id)
    except Exception as e:
        logger.error(f"Failed to save results for job {job_id}: {e}")
        raise e


@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def create_detection_images(source_image_ids: list[int]):
    from ami.main.models import SourceImage

    start_time = time.time()

    logger.debug(f"Creating detection images for {len(source_image_ids)} capture(s)")

    for source_image in SourceImage.objects.filter(pk__in=source_image_ids):
        try:
            processed_paths = create_detection_images_from_source_image(source_image)
            logger.debug(f"Created {len(processed_paths)} detection images for SourceImage #{source_image.pk}")
        except Exception as e:
            logger.error(f"Error creating detection images for SourceImage {source_image.pk}: {str(e)}")

    total_time = time.time() - start_time
    logger.info(f"Created detection images for {len(source_image_ids)} capture(s) in {total_time:.2f} seconds")


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


# Timeout for get_status() calls in the periodic beat task. Shorter than the default (90s)
# because we don't need to wait for cold starts here — if a service is starting up it will
# recover on the next check. With retries=3 and backoff_factor=2, worst case per service
# is roughly: 8 + 2 + 8 + 4 + 8 = 30s.
_BEAT_STATUS_TIMEOUT = 8


@celery_app.task(soft_time_limit=120, time_limit=150)
def check_processing_services_online():
    """
    Check the status of all processing services and update last_seen/last_seen_live fields.

    - Async services (no endpoint URL): heartbeat is updated by mark_seen() on registration
      and by _mark_pipeline_pull_services_seen() on task polling. This task marks them offline
      if last_seen has exceeded PROCESSING_SERVICE_LAST_SEEN_MAX. Runs first so it always
      executes even if a sync service check is slow.
    - Sync services (endpoint URL set): actively polled via /readyz. Uses a reduced timeout
      vs. the default (which is designed for cold-start waits) since missed checks recover
      on the next beat cycle.

    @TODO make this async to check all services in parallel
    """
    import datetime

    from ami.ml.models.processing_service import PROCESSING_SERVICE_LAST_SEEN_MAX, ProcessingService

    logger.info("Checking which processing services are online.")

    # Async services first — fast DB-only operation, must not be skipped by a slow sync check
    stale_cutoff = datetime.datetime.now() - PROCESSING_SERVICE_LAST_SEEN_MAX
    stale = ProcessingService.objects.async_services().filter(last_seen_live=True, last_seen__lt=stale_cutoff)
    count = stale.count()
    if count:
        logger.info(
            f"Marking {count} async service(s) offline (no heartbeat within {PROCESSING_SERVICE_LAST_SEEN_MAX})."
        )
        stale.update(last_seen_live=False)

    for service in ProcessingService.objects.sync_services():
        logger.info(f"Checking push-mode service {service}")
        try:
            status_response = service.get_status(timeout=_BEAT_STATUS_TIMEOUT)
            logger.debug(status_response)
        except Exception as e:
            logger.error(f"Error checking service {service}: {e}")
            continue
