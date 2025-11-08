import datetime
import logging
import time

from ami.ml.media import create_detection_images_from_source_image
from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


# @TODO: Deprecate this? is this still needed?
@celery_app.task(soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def process_source_images_async(pipeline_choice: str, image_ids: list[int], job_id: int | None):
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
    project = pipeline.projects.first()
    assert project, f"Pipeline {pipeline} must be associated with a project."

    results = process_images(pipeline=pipeline, images=images, job_id=job_id, project_id=project.pk)

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


@celery_app.task(soft_time_limit=10, time_limit=20)
def check_processing_services_online():
    """
    Check the status of all processing services and update last checked.

    @TODO make this async to check all services in parallel
    """
    from ami.ml.models import ProcessingService

    logger.info("Checking if processing services are online.")

    services = ProcessingService.objects.all()

    for service in services:
        logger.info(f"Checking service {service}")
        try:
            status_response = service.get_status()
            logger.debug(status_response)
        except Exception as e:
            logger.error(f"Error checking service {service}: {e}")
            continue


@celery_app.task()  # TODO: add a time limit? stay active for as long as the ML job will take
def check_ml_job_status(ml_job_id: int):
    """
    Check the status of a specific ML job's inprogress subtasks and update its status accordingly.
    """
    from ami.jobs.models import Job, JobState, MLJob

    job = Job.objects.get(pk=ml_job_id)
    assert job.job_type_key == MLJob.key, f"{ml_job_id} is not an ML job."

    try:
        logger.info(f"Checking status for job {job}.")
        logger.info(f"Job subtasks are: {job.ml_task_records.all()}.")
        jobs_complete = job.check_inprogress_subtasks()
        logger.info(f"Successfully checked status for job {job}. .")
        job.last_checked = datetime.datetime.now()
        job.save(update_fields=["last_checked"])

        if jobs_complete:
            logger.info(f"ML Job {ml_job_id} is complete.")
            job.logger.info(f"ML Job {ml_job_id} is complete.")
        else:
            from django.db import transaction

            logger.info(f"ML Job {ml_job_id} still in progress. Checking again for completed tasks.")
            transaction.on_commit(lambda: check_ml_job_status.apply_async([ml_job_id], countdown=5))
    except Job.DoesNotExist:
        raise ValueError(f"Job with ID {ml_job_id} does not exist.")
    except Exception as e:
        error_msg = f"Error checking status for job with ID {ml_job_id}: {e}"
        job.logger.error(error_msg)
        job.update_status(JobState.FAILURE)
        job.finished_at = datetime.datetime.now()
        job.save()

        # Remove remaining tasks from the queue
        for ml_task_record in job.ml_task_records.all():
            ml_task_record.kill_task()

        raise Exception(error_msg)


@celery_app.task(soft_time_limit=600, time_limit=800)
def check_dangling_ml_jobs():
    """
    An inprogress ML job is dangling if the last_checked time
    is older than 5 minutes.
    """
    import datetime

    from ami.jobs.models import Job, JobState, MLJob

    inprogress_jobs = Job.objects.filter(job_type_key=MLJob.key, status=JobState.STARTED.name)
    logger.info(f"Found {inprogress_jobs.count()} inprogress ML jobs to check for dangling tasks.")

    for job in inprogress_jobs:
        last_checked = job.last_checked
        if not last_checked:
            logger.warning(f"Job {job.pk} has no last_checked time. Marking as dangling.")
            seconds_since_checked = float("inf")
        else:
            seconds_since_checked = (datetime.datetime.now() - last_checked).total_seconds()
        if last_checked is None or seconds_since_checked > 24 * 60 * 60:  # 24 hours
            logger.warning(
                f"Job {job.pk} appears to be dangling since {last_checked} "
                f"was {seconds_since_checked} ago. Marking as failed."
            )
            job.logger.error(
                f"Job {job.pk} appears to be dangling since {last_checked} "
                f"was {seconds_since_checked} ago. Marking as failed."
            )
            job.update_status(JobState.REVOKED)
            job.finished_at = datetime.datetime.now()
            job.save()

            for ml_task_record in job.ml_task_records.all():
                ml_task_record.kill_task()
        else:
            logger.info(f"Job {job.pk} is active. Last checked at {last_checked}.")
