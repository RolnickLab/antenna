import datetime
import logging

from celery.result import AsyncResult
from celery.signals import task_failure, task_postrun, task_prerun

from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def initialize_ml_job(self, job_id: int) -> None:
    """
    Initialize an ML job by collecting images and creating image processing tasks
    """
    from ami.jobs.models import Job, JobState

    job = Job.objects.get(pk=job_id)
    job.logger.info(f"Initializing ML job {job}")

    try:
        # Set up the job status
        job.update_status(JobState.STARTED)

        # Handle delay if specified
        if job.delay:
            job.logger.info(f"Delaying job {job.pk} for {job.delay} seconds")
            job.progress.update_stage(
                "delay",
                status=JobState.STARTED,
                progress=0,
                mood="😴",
            )
            process_delay.apply_async(kwargs={"job_id": job.pk, "delay": job.delay})
            return

        # Proceed with image collection
        job.progress.update_stage(
            "collect",
            status=JobState.STARTED,
            progress=0,
        )
        job.save()

        # Collect images (this is the potentially long-running part)
        collect_images_for_ml_job.apply_async(kwargs={"job_id": job.pk})

    except Exception as e:
        job.logger.error(f'ML job initialization #{job.pk} "{job.name}" failed: {e}')
        job.update_status(JobState.FAILURE)
        job.save()
        raise


@celery_app.task(bind=True, soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def initialize_job(self, job_id: int) -> None:
    """
    Initialize a job by determining what type of job it is and how to split it into tasks.
    This task replaces the original run_job task as the entry point for job execution.
    """
    from ami.jobs.models import DataStorageSyncJob, Job, JobState, MLJob, SourceImageCollectionPopulateJob

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist as e:
        logger.error(f"Job {job_id} does not exist")
        raise e

    job.logger.info(f"Initializing job {job}")
    job.update_status(JobState.STARTED)
    job.started_at = datetime.datetime.now()
    job.save()

    try:
        # Handle different job types with specialized initialization
        job_type_key = job.job_type_key

        if job_type_key == MLJob.key:
            initialize_ml_job(job_id=job_id)
        elif job_type_key == DataStorageSyncJob.key:
            initialize_storage_sync_job(job_id)
        elif job_type_key == SourceImageCollectionPopulateJob.key:
            initialize_collection_populate_job(job_id)
        else:
            # Fall back to the legacy direct run approach for unknown job types
            run_job(job_id=job_id)

    except Exception as e:
        job.logger.error(f'Job initialization #{job.pk} "{job.name}" failed: {e}')
        job.update_status(JobState.FAILURE)
        job.save()
        raise


@celery_app.task(bind=True)
def process_delay(self, job_id: int, delay: int) -> None:
    """Process a delay for a job"""
    import time

    from ami.jobs.models import Job, JobState

    job = Job.objects.get(pk=job_id)
    update_interval_seconds = 2
    last_update = time.time()

    job.logger.info(f"Processing delay of {delay} seconds for job {job_id}")

    for i in range(delay):
        time.sleep(1)
        # Update periodically
        if time.time() - last_update > update_interval_seconds:
            job.logger.info(f"Delaying job {job.pk} for {i+1} out of {delay} seconds")
            job.progress.update_stage(
                "delay",
                status=JobState.STARTED,
                progress=i / delay,
                mood="😵‍💫",
            )
            job.save()
            last_update = time.time()

    # Delay complete, update stage
    job.progress.update_stage(
        "delay",
        status=JobState.SUCCESS,
        progress=1,
        mood="🥳",
    )
    job.save()

    # Continue with image collection
    collect_images_for_ml_job.apply_async(kwargs={"job_id": job.pk})


@celery_app.task(bind=True)
def collect_images_for_ml_job(self, job_id: int) -> None:
    """Collect images for an ML job and create processing tasks"""
    import random

    from ami.jobs.models import Job, JobState

    job = Job.objects.get(pk=job_id)

    try:
        if not job.pipeline:
            raise ValueError("No pipeline specified to process images in ML job")

        # Collect images
        job.progress.update_stage(
            "collect",
            status=JobState.STARTED,
            progress=0,
        )
        job.save()

        images = list(
            job.pipeline.collect_images(
                collection=job.source_image_collection,
                deployment=job.deployment,
                source_images=[job.source_image_single] if job.source_image_single else None,
                job_id=job.pk,
                skip_processed=True,
            )
        )
        source_image_count = len(images)
        job.progress.update_stage("collect", total_images=source_image_count)

        # Apply shuffling if requested
        if job.shuffle and source_image_count > 1:
            job.logger.info("Shuffling images")
            random.shuffle(images)

        # Apply limit if requested
        if job.limit and source_image_count > job.limit:
            job.logger.info(f"Limiting number of images to {job.limit} (out of {source_image_count})")
            images = images[: job.limit]
            image_count = len(images)
            job.progress.add_stage_param("collect", "Limit", image_count)
        else:
            image_count = source_image_count

        # Mark collection stage as complete
        job.progress.update_stage(
            "collect",
            status=JobState.SUCCESS,
            progress=1,
        )
        job.save()

        # Create image processing tasks
        config = job.pipeline.get_config(project_id=job.project.pk)
        chunk_size = config.get("request_source_image_batch_size", 10)
        chunks = [images[i : i + chunk_size] for i in range(0, image_count, chunk_size)]  # noqa: E203

        # Set up task tracking
        job.total_tasks = len(chunks)
        job.pending_tasks = len(chunks)
        job.save()

        # Create processing tasks
        queue_name = job.get_task_queue_name()
        job.logger.info(f"Creating {len(chunks)} image processing tasks in queue '{queue_name}'")

        # Create or update process stage
        job.progress.update_stage(
            "process",
            status=JobState.STARTED,
            progress=0,
            total_chunks=len(chunks),
            processed_chunks=0,
        )
        job.save()

        # Ensure task counters are set
        job.total_tasks = len(chunks)
        job.pending_tasks = len(chunks)
        job.completed_tasks = 0
        job.failed_tasks = 0
        job.save()

        # Launch all tasks with links to the queue name
        for i, chunk in enumerate(chunks):
            job.logger.info(f"Queueing chunk {i+1}/{len(chunks)} with {len(chunk)} images to queue '{queue_name}'")
            process_image_chunk.apply_async(
                kwargs={
                    "job_id": job.pk,
                    "chunk_index": i,
                    "image_ids": [img.pk for img in chunk],
                    "total_chunks": len(chunks),
                },
                queue=queue_name,
            )

        # Log clear diagnostics about the queuing
        job.logger.info(f"All {len(chunks)} chunks have been queued for processing in queue '{queue_name}'")
        job.logger.info("Workers with queue pattern 'job_ml_*' should pick up these tasks")
        job.logger.info("Monitoring job completion status with periodic checks")

        # Schedule a monitoring task
        check_job_completion.apply_async(kwargs={"job_id": job.pk}, countdown=10)  # Check after 10 seconds initially

    except Exception as e:
        job.logger.error(f"Error collecting images for job {job.pk}: {e}")
        job.update_status(JobState.FAILURE)
        job.save()
        raise


@celery_app.task(bind=True)
def process_image_chunk(self, job_id: int, chunk_index: int, image_ids: list[int], total_chunks: int) -> None:
    """Process a chunk of images for an ML job"""
    import time

    from ami.jobs.models import Job, JobState
    from ami.main.models import SourceImage

    job = Job.objects.get(pk=job_id)

    try:
        # Get source images for this chunk
        images = list(SourceImage.objects.filter(pk__in=image_ids))
        job.logger.info(f"Processing chunk {chunk_index+1}/{total_chunks} with {len(images)} images")

        if not job.pipeline:
            raise ValueError("No pipeline specified for this job")

        # Process the images
        request_sent = time.time()
        results = job.pipeline.process_images(
            images=images,
            job_id=job.pk,
            project_id=job.project.pk,
        )
        job.logger.info(f"Processed chunk {chunk_index+1} in {time.time() - request_sent:.2f}s")

        # Save results asynchronously
        if results.source_images or results.detections:
            save_results_task = job.pipeline.save_results_async(results=results, job_id=job.pk)
            job.logger.info(f"Saving results for chunk {chunk_index+1} in sub-task {save_results_task.id}")

            # Wait for save_results task to complete (with timeout)
            # Note: We wait here to ensure data consistency, but with a reasonable timeout
            save_results_task.get(timeout=300, disable_sync_subtasks=False)

        # Update job progress
        job.progress.update_stage(
            "process",
            status=JobState.STARTED,
            progress=(chunk_index + 1) / total_chunks,
            processed=(chunk_index + 1) * len(images),
        )

        # Update task counters
        job.update_task_counters(completed=1, pending=-1)

        # Return success message - not actually used by Celery
        job.logger.info(f"Processed chunk {chunk_index+1}/{total_chunks} for job {job_id}")

    except Exception as e:
        job.logger.error(f"Error processing chunk {chunk_index+1} for job {job.pk}: {e}")
        job.update_task_counters(failed=1, pending=-1)
        raise


@celery_app.task(bind=True)
def initialize_storage_sync_job(self, job_id: int) -> None:
    """Initialize a storage sync job"""
    from ami.jobs.models import Job

    job = Job.objects.get(pk=job_id)
    job.logger.info(f"Initializing storage sync job {job}")

    # For now, we'll use the legacy direct run approach for this job type
    # In the future, this could be enhanced to break down sync tasks by directories
    run_job(job_id=job_id)


@celery_app.task(bind=True)
def initialize_collection_populate_job(self, job_id: int) -> None:
    """Initialize a collection populate job"""
    from ami.jobs.models import Job

    job = Job.objects.get(pk=job_id)
    job.logger.info(f"Initializing collection populate job {job}")

    # For now, we'll use the legacy direct run approach for this job type
    # In the future, this could be enhanced to break down collection population into chunks
    run_job(job_id=job_id)


@celery_app.task(bind=True)
def check_job_completion(self, job_id: int) -> None:
    """Periodically check if all tasks for a job have completed"""
    from ami.jobs.models import Job, JobState

    job = Job.objects.get(pk=job_id)
    job.logger.info(
        f"Checking job completion status: pending={job.pending_tasks}, completed={job.completed_tasks}, "
        f"failed={job.failed_tasks}, total={job.total_tasks}"
    )

    # If job is in a final state but we still have pending tasks, something's wrong - reset the status
    if job.status in JobState.final_states() and job.pending_tasks > 0 and job.total_tasks > 0:
        job.logger.warning(
            f"Job is marked as {job.status} but still has {job.pending_tasks} pending tasks. Resetting to STARTED."
        )
        job.update_status(JobState.STARTED)

    # If all tasks are complete or failed
    if job.completed_tasks + job.failed_tasks >= job.total_tasks and job.total_tasks > 0:
        # Final job update - will set appropriate status based on task statistics
        success_ratio = job.completed_tasks / job.total_tasks if job.total_tasks > 0 else 0
        job.logger.info(
            f"All tasks complete: {job.completed_tasks} successful, {job.failed_tasks} failed - success ratio: "
            f"{success_ratio:.2%}"
        )

        # Update process stage to complete
        job.progress.update_stage(
            "process",
            status=JobState.SUCCESS if success_ratio > 0.5 else JobState.FAILURE,
            progress=1,
        )

        # Update results stage
        job.progress.update_stage(
            "results",
            status=JobState.SUCCESS if success_ratio > 0.5 else JobState.FAILURE,
            progress=1,
        )

        # Set final job status
        if success_ratio > 0.5:
            job.update_status(JobState.SUCCESS, save=False)
        else:
            job.update_status(JobState.FAILURE, save=False)

        job.finished_at = datetime.datetime.now()
        job.save()
        job.logger.info(
            f"Job {job_id} marked as {job.status} with {job.completed_tasks}/{job.total_tasks} tasks succeeded"
        )
        return

    # Check if there are any pending tasks but the job was just created
    if job.pending_tasks == 0 and job.completed_tasks == 0 and job.failed_tasks == 0 and job.total_tasks > 0:
        job.logger.warning(
            f"Job has {job.total_tasks} total tasks but no pending/completed/failed tasks. Resetting pending counter."
        )
        job.pending_tasks = job.total_tasks
        job.save()

    # Log progress and reschedule check
    job.logger.info(
        f"Job still in progress: {job.completed_tasks + job.failed_tasks}/{job.total_tasks} tasks complete"
    )
    # Use a shorter interval for the first few checks, then longer intervals
    if job.completed_tasks + job.failed_tasks < 5:
        countdown = 10  # Check more frequently at first
    else:
        countdown = 30  # Then less frequently

    check_job_completion.apply_async(kwargs={"job_id": job_id}, countdown=countdown)


# Legacy tasks - kept for backward compatibility and as fallbacks


@celery_app.task(bind=True, soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def run_job(self, job_id: int) -> None:
    """
    Legacy task that directly runs a job without queue-based coordination.
    Kept for backward compatibility and as a fallback for job types that
    haven't been migrated to the new system.
    """
    from ami.jobs.models import Job

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist as e:
        raise e
    else:
        job.logger.info(f"Running job {job} using legacy direct execution")
        try:
            job.run()
        except Exception as e:
            job.logger.error(f'Job #{job.pk} "{job.name}" failed: {e}')
            raise
        else:
            job.refresh_from_db()
            job.logger.info(f"Finished job {job}")


@task_postrun.connect(sender=run_job)
@task_postrun.connect(sender=initialize_job)
@task_prerun.connect(sender=run_job)
@task_prerun.connect(sender=initialize_job)
def update_job_status(sender, task_id, task, *args, **kwargs):
    """Update job status based on task status"""
    from ami.jobs.models import Job

    if not hasattr(task.request, "kwargs") or "job_id" not in task.request.kwargs:
        return

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

    task_result = AsyncResult(task_id)
    job.update_status(task_result.status, save=False)
    job.save()


@task_failure.connect(sender=run_job)
@task_failure.connect(sender=initialize_job)
@task_failure.connect(sender=initialize_ml_job)
@task_failure.connect(sender=process_image_chunk)
def update_job_failure(sender, task_id, exception, *args, **kwargs):
    """Mark a job as failed when a task fails"""
    from ami.jobs.models import Job, JobState

    try:
        if not hasattr(kwargs.get("task", {}), "request") or not hasattr(kwargs["task"].request, "kwargs"):
            return

        if "job_id" not in kwargs["task"].request.kwargs:
            return

        job_id = kwargs["task"].request.kwargs["job_id"]
        job = Job.objects.get(pk=job_id)
        job.update_status(JobState.FAILURE, save=False)
        job.logger.error(f'Job #{job.pk} "{job.name}" failed: {exception}')
        job.save()
    except Exception as e:
        logger.error(f"Error updating job failure status: {e}")
