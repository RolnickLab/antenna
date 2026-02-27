import datetime
import logging
import random
import time
import typing
from dataclasses import dataclass

import pydantic
from celery import uuid
from celery.result import AsyncResult
from django.db import models, transaction
from django.utils.text import slugify
from django_pydantic_field import SchemaField
from guardian.shortcuts import get_perms

from ami.base.models import BaseModel
from ami.base.schemas import ConfigurableStage, ConfigurableStageParam
from ami.jobs.tasks import run_job
from ami.main.models import Deployment, Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.post_processing.registry import get_postprocessing_task
from ami.utils.schemas import OrderedEnum

logger = logging.getLogger(__name__)


class JobDispatchMode(models.TextChoices):
    """
    How a job dispatches its workload.

    Jobs are configured and launched by users in the UI, then dispatched to
    Celery workers. This enum describes what the worker does with the work:

    - INTERNAL: All work happens within the platform (Celery worker handles it directly).
    - SYNC_API: Worker calls an external processing service API and waits for each response.
    - ASYNC_API: Worker queues items to a message broker (NATS) for external processing
      service workers to pick up and process independently.
    """

    # Work is handled entirely within the platform, no external service calls.
    # e.g. DataStorageSyncJob, DataExportJob, SourceImageCollectionPopulateJob
    INTERNAL = "internal", "Internal"

    # Worker loops over items, sends each to an external processing service
    # endpoint synchronously, and waits for the response before continuing.
    SYNC_API = "sync_api", "Sync API"

    # Worker publishes all items to a message broker (NATS). External processing
    # service workers consume and process them independently, reporting results back.
    ASYNC_API = "async_api", "Async API"


class JobState(str, OrderedEnum):
    """
    These come from Celery, except for CREATED, which is a custom state.
    """

    # CREATED = "Created"
    # PENDING = "Pending"
    # STARTED = "Started"
    # SUCCESS = "Succeeded"
    # FAILURE = "Failed"
    # RETRY = "Retrying"
    # REVOKED = "Revoked"
    # RECEIVED = "Received"

    # Using same value for name and value for now.
    CREATED = "CREATED"
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    CANCELING = "CANCELING"
    REVOKED = "REVOKED"
    RECEIVED = "RECEIVED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def running_states(cls):
        return [cls.CREATED, cls.PENDING, cls.STARTED, cls.RETRY, cls.CANCELING, cls.UNKNOWN]

    @classmethod
    def final_states(cls):
        return [cls.SUCCESS, cls.FAILURE, cls.REVOKED]

    @classmethod
    def failed_states(cls):
        return [cls.FAILURE, cls.REVOKED, cls.UNKNOWN]


def get_status_label(status: JobState, progress: float) -> str:
    """
    A human label of the status and progress percent in a single string.
    """
    if not isinstance(status, JobState):
        status = JobState(status)
    if status in [JobState.CREATED, JobState.PENDING, JobState.RECEIVED]:
        return "Waiting to start"
    elif status in [JobState.STARTED, JobState.RETRY, JobState.SUCCESS]:
        return f"{progress:.0%} complete"
    else:
        return f"{status.name}"


def python_slugify(value: str) -> str:
    # Use underscore instead of dash so we can use them as python property names
    return slugify(value, allow_unicode=False).replace("-", "_")


class JobProgressSummary(pydantic.BaseModel):
    """Top-level status and progress for a job, shown in the UI."""

    status: JobState = JobState.CREATED
    progress: float = 0

    @property
    def status_label(self) -> str:
        return get_status_label(self.status, self.progress)

    class Config:
        use_enum_values = True


class JobProgressStageDetail(ConfigurableStage, JobProgressSummary):
    """A stage of a job"""

    pass


stage_parameters = JobProgressStageDetail.__fields__.keys()


class JobProgress(pydantic.BaseModel):
    """
    The user-facing progress of a job, stored as JSONB on the Job model.

    This is what the UI displays and what external APIs read. Contains named
    stages ("process", "results") with per-stage params (progress percentage,
    detections/classifications/captures counts, failed count).

    For async (NATS) jobs, updated by _update_job_progress() in ami/jobs/tasks.py
    which copies snapshots from the internal Redis-backed AsyncJobStateManager.
    For sync jobs, updated directly in MLJob.process_images().
    """

    summary: JobProgressSummary
    stages: list[JobProgressStageDetail]
    errors: list[str] = []  # Deprecated, @TODO remove in favor of logs.stderr
    logs: list[str] = []  # Deprecated, @TODO remove in favor of logs.stdout

    def make_key(self, name: str) -> str:
        """Generate a key for a stage or param based on its name"""
        return python_slugify(name)

    def add_stage(self, name: str, key: str | None = None) -> JobProgressStageDetail:
        key = key or self.make_key(name)
        try:
            return self.get_stage(key)
        except ValueError:
            stage = JobProgressStageDetail(
                key=key,
                name=name,
            )
            self.stages.append(stage)
            return stage

    def get_stage(self, stage_key: str) -> JobProgressStageDetail:
        for stage in self.stages:
            if stage.key == stage_key:
                return stage
        raise ValueError(f"Job stage with key '{stage_key}' not found in progress")

    def get_stage_param(self, stage_key: str, param_key: str) -> ConfigurableStageParam:
        stage = self.get_stage(stage_key)
        for param in stage.params:
            if param.key == param_key:
                return param
        raise ValueError(f"Job stage parameter with key '{param_key}' not found in stage '{stage_key}'")

    def add_stage_param(self, stage_key: str, param_name: str, value: typing.Any = None) -> ConfigurableStageParam:
        stage = self.get_stage(stage_key)
        try:
            return self.get_stage_param(stage_key, self.make_key(param_name))
        except ValueError:
            param = ConfigurableStageParam(
                name=param_name,
                key=self.make_key(param_name),
                value=value,
            )
            stage.params.append(param)
            return param

    def add_or_update_stage_param(
        self, stage_key: str, param_name: str, value: typing.Any = None
    ) -> ConfigurableStageParam:
        try:
            param = self.get_stage_param(stage_key, self.make_key(param_name))
            param.value = value
            return param
        except ValueError:
            return self.add_stage_param(stage_key, param_name, value)

    def update_stage(self, stage_key_or_name: str, **stage_parameters) -> JobProgressStageDetail | None:
        """ "
        Update the parameters of a stage of the job.

        Will update parameters that are direct attributes of the stage,
        or parameters that are in the stage's params list.

        This is the preferred method to update a stage's parameters.
        """
        stage_key = self.make_key(stage_key_or_name)  # Allow both title or key to be used for lookup
        stage = self.get_stage(stage_key)

        if stage.key == stage_key:
            for k, v in stage_parameters.items():
                # Update a matching attribute directly on the stage object first
                if hasattr(stage, k):
                    setattr(stage, k, v)
                else:
                    # Otherwise update or add matching parameter within the stage's params list
                    self.add_or_update_stage_param(stage_key, k, v)
            return stage

    def reset(self, status: JobState = JobState.CREATED):
        """
        Set the progress of summary and all stages to 0.
        """
        self.summary.progress = 0
        self.summary.status = status
        for stage in self.stages:
            stage.progress = 0
            stage.status = status
            # Reset numeric param values to 0
            for param in stage.params:
                if isinstance(param.value, (int, float)):
                    param.value = 0

    def is_complete(self) -> bool:
        """
        Check if all stages have finished processing.

        A job is considered complete when ALL of its stages have:
        - progress >= 1.0 (fully processed)
        - status in a final state (SUCCESS, FAILURE, or REVOKED)

        This method works for any job type regardless of which stages it has.
        It's used by the Celery task_postrun signal to determine whether to
        set the job's final SUCCESS status, or defer to async progress handlers.

        Related: Job.update_progress() calculates the aggregate
        progress percentage across all stages for display purposes. This method
        is a binary check for completion that considers both progress AND status.

        Returns:
            True if all stages are complete, False otherwise.
            Returns False if job has no stages (shouldn't happen in practice).
        """
        if not self.stages:
            return False
        return all(stage.progress >= 1.0 and stage.status in JobState.final_states() for stage in self.stages)

    class Config:
        use_enum_values = True
        as_dict = True


def default_job_progress() -> JobProgress:
    return JobProgress(
        summary=JobProgressSummary(status=JobState.CREATED, progress=0),
        stages=[],
    )


def default_ml_job_progress() -> JobProgress:
    """
    Default stages for an ML Job.

    @TODO add this to the get_default_progress() method of the
    MLJob class, or delete it. Currently unused.
    """
    return JobProgress(
        summary=JobProgressSummary(status=JobState.CREATED, progress=0),
        stages=[
            JobProgressStageDetail(
                key="object_detection",
                name="Object Detection",
                status=JobState.CREATED,
                progress=0,
            ),
            JobProgressStageDetail(
                key="binary_classification",
                name="Objects of Interest Filter",
                status=JobState.CREATED,
                progress=0,
            ),
            JobProgressStageDetail(
                key="species_classification",
                name="Species Classification",
                status=JobState.CREATED,
                progress=0,
            ),
            JobProgressStageDetail(
                key="tracking",
                name="Occurrence Tracking",
                status=JobState.CREATED,
                progress=0,
            ),
        ],
    )


class JobLogs(pydantic.BaseModel):
    stdout: list[str] = pydantic.Field(default_factory=list, alias="stdout", title="All messages")
    stderr: list[str] = pydantic.Field(default_factory=list, alias="stderr", title="Error messages")


class JobLogHandler(logging.Handler):
    """
    Class for handling logs from a job and writing them to the job instance.
    """

    max_log_length = 1000

    def __init__(self, job: "Job", *args, **kwargs):
        self.job = job
        super().__init__(*args, **kwargs)

    def emit(self, record: logging.LogRecord):
        # Log to the current app logger
        logger.log(record.levelno, self.format(record))

        # Write to the logs field on the job instance
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{timestamp}] {record.levelname} {self.format(record)}"
        if msg not in self.job.logs.stdout:
            self.job.logs.stdout.insert(0, msg)

        # Write a simpler copy of any errors to the errors field
        if record.levelno >= logging.ERROR:
            if record.message not in self.job.logs.stderr:
                self.job.logs.stderr.insert(0, record.message)

        if len(self.job.logs.stdout) > self.max_log_length:
            self.job.logs.stdout = self.job.logs.stdout[: self.max_log_length]

        # @TODO consider saving logs to the database periodically rather than on every log
        try:
            self.job.save(update_fields=["logs"], update_progress=False)
        except Exception as e:
            logger.error(f"Failed to save logs for job #{self.job.pk}: {e}")
            pass


@dataclass
class JobType:
    """
    The run method of a job is specific to the job type.

    Job types must be defined as classes because they define code, not just configuration.
    """

    name: str
    key: str

    # @TODO Consider adding custom vocabulary for job types to be used in the UI
    # verb: str = "Sync"
    # present_participle: str = "syncing"
    # past_participle: str = "synced"

    @classmethod
    def run(cls, job: "Job"):
        """
        Execute the run function specific to this job type.
        """
        raise NotImplementedError("Job type has not implemented the run method")


class MLJob(JobType):
    name = "ML pipeline"
    key = "ml"

    @classmethod
    def run(cls, job: "Job"):
        """
        Procedure for an ML pipeline as a job.
        """
        from ami.ml.orchestration.jobs import queue_images_to_nats

        job.update_status(JobState.STARTED)
        job.started_at = datetime.datetime.now()
        job.finished_at = None
        job.save()

        if job.delay:
            update_interval_seconds = 2
            last_update = time.time()
            for i in range(job.delay):
                time.sleep(1)
                # Update periodically
                if time.time() - last_update > update_interval_seconds:
                    job.logger.info(f"Delaying job {job.pk} for the {i} out of {job.delay} seconds")
                    job.progress.update_stage(
                        "delay",
                        status=JobState.STARTED,
                        progress=i / job.delay,
                        mood="😵‍💫",
                    )
                    job.save()
                    last_update = time.time()

            job.progress.update_stage(
                "delay",
                status=JobState.SUCCESS,
                progress=1,
                mood="🥳",
            )
            job.save()

        if not job.pipeline:
            raise ValueError("No pipeline specified to process images in ML job")

        job.progress.update_stage(
            "collect",
            status=JobState.STARTED,
            progress=0,
        )

        images: list[SourceImage] = list(
            # @TODO return generator plus image count
            # @TODO pass to celery group chain?
            job.pipeline.collect_images(
                collection=job.source_image_collection,
                deployment=job.deployment,
                source_images=[job.source_image_single] if job.source_image_single else None,
                job_id=job.pk,
                reprocess_all_images=job.project.feature_flags.reprocess_all_images,
                # shuffle=job.shuffle,
            )
        )
        source_image_count = len(images)
        job.progress.update_stage("collect", total_images=source_image_count)

        if job.shuffle and source_image_count > 1:
            job.logger.info("Shuffling images")
            random.shuffle(images)

        if job.limit and source_image_count > job.limit:
            job.logger.warn(f"Limiting number of images to {job.limit} (out of {source_image_count})")
            images = images[: job.limit]
            image_count = len(images)
            job.progress.add_stage_param("collect", "Limit", image_count)

        job.progress.update_stage(
            "collect",
            status=JobState.SUCCESS,
            progress=1,
        )

        # End image collection stage
        job.save()

        if job.dispatch_mode == JobDispatchMode.ASYNC_API:
            queued = queue_images_to_nats(job, images)
            if not queued:
                job.logger.error("Aborting job %s because images could not be queued to NATS", job.pk)
                job.progress.update_stage("collect", status=JobState.FAILURE)
                job.update_status(JobState.FAILURE)
                job.finished_at = datetime.datetime.now()
                job.save()
                return
        else:
            cls.process_images(job, images)

    @classmethod
    def process_images(cls, job, images):
        image_count = len(images)
        # Keep track of sub-tasks for saving results, pair with batch number
        save_tasks: list[tuple[int, AsyncResult]] = []
        save_tasks_completed: list[tuple[int, AsyncResult]] = []
        total_captures = 0
        total_detections = 0
        total_classifications = 0

        config = job.pipeline.get_config(project_id=job.project.pk)
        chunk_size = config.get("request_source_image_batch_size", 1)
        chunks = [images[i : i + chunk_size] for i in range(0, image_count, chunk_size)]  # noqa
        request_failed_images = []
        job.logger.info(f"Processing {image_count} images in {len(chunks)} batches of up to {chunk_size}")

        for i, chunk in enumerate(chunks):
            request_sent = time.time()
            job.logger.info(f"Processing image batch {i+1} of {len(chunks)}")
            try:
                results = job.pipeline.process_images(
                    images=chunk,
                    job_id=job.pk,
                    project_id=job.project.pk,
                    reprocess_all_images=job.project.feature_flags.reprocess_all_images,
                )
                job.logger.info(f"Processed image batch {i+1} in {time.time() - request_sent:.2f}s")
            except Exception as e:
                # Log error about image batch and continue
                job.logger.error(f"Failed to process image batch {i+1}: {e}")
                request_failed_images.extend([img.pk for img in chunk])
            else:
                total_captures += len(results.source_images)
                total_detections += len(results.detections)
                total_classifications += len([c for d in results.detections for c in d.classifications])

                if results.source_images or results.detections:
                    # @TODO add callback to report errors while saving results marking the job as failed
                    save_results_task: AsyncResult = job.pipeline.save_results_async(results=results, job_id=job.pk)
                    save_tasks.append((i + 1, save_results_task))
                    job.logger.info(f"Saving results for batch {i+1} in sub-task {save_results_task.id}")

            job.progress.update_stage(
                "process",
                status=JobState.STARTED,
                progress=(i + 1) / len(chunks),
                processed=min((i + 1) * chunk_size, image_count),
                failed=len(request_failed_images),
                remaining=max(image_count - ((i + 1) * chunk_size), 0),
            )

            # count the completed, successful, and failed save_tasks:
            save_tasks_completed = [t for t in save_tasks if t[1].ready()]
            failed_save_tasks = [t for t in save_tasks_completed if not t[1].successful()]

            for failed_batch_num, failed_task in failed_save_tasks:
                # First log all errors and update the job status. Then raise exception if any failed.
                job.logger.error(f"Failed to save results from batch {failed_batch_num} (sub-task {failed_task.id})")

            job.progress.update_stage(
                "results",
                status=JobState.FAILURE if failed_save_tasks else JobState.STARTED,
                progress=len(save_tasks_completed) / len(chunks),
                captures=total_captures,
                detections=total_detections,
                classifications=total_classifications,
            )
            job.save()

            # Stop processing if any save tasks have failed
            # Otherwise, calculate the percent of images that have failed to save
            throw_on_save_error = True
            for failed_batch_num, failed_task in failed_save_tasks:
                if throw_on_save_error:
                    failed_task.maybe_throw()

        if image_count:
            percent_successful = 1 - len(request_failed_images) / image_count if image_count else 0
            job.logger.info(f"Processed {percent_successful:.0%} of images successfully.")

        # Check all Celery sub-tasks if they have completed saving results
        save_tasks_remaining = set(save_tasks) - set(save_tasks_completed)
        job.logger.info(
            f"Checking the status of {len(save_tasks_remaining)} remaining sub-tasks that are still saving results."
        )
        for batch_num, sub_task in save_tasks:
            if not sub_task.ready():
                job.logger.info(f"Waiting for batch {batch_num} to finish saving results (sub-task {sub_task.id})")
                # @TODO this is not recommended! Use a group or chain. But we need to refactor.
                # https://docs.celeryq.dev/en/latest/userguide/tasks.html#avoid-launching-synchronous-subtasks
                sub_task.wait(disable_sync_subtasks=False, timeout=60)
            if not sub_task.successful():
                error: Exception = sub_task.result
                job.logger.error(f"Failed to save results from batch {batch_num}! (sub-task {sub_task.id}): {error}")
                sub_task.maybe_throw()

        job.logger.info(f"All tasks completed for job {job.pk}")

        from ami.jobs.tasks import FAILURE_THRESHOLD

        if image_count and (percent_successful < FAILURE_THRESHOLD):
            job.progress.update_stage("process", status=JobState.FAILURE)
            job.save()
            raise Exception(f"Failed to process more than {int(FAILURE_THRESHOLD * 100)}% of images")

        job.progress.update_stage(
            "process",
            status=JobState.SUCCESS,
            progress=1,
        )
        job.progress.update_stage(
            "results",
            status=JobState.SUCCESS,
            progress=1,
        )
        job.update_status(JobState.SUCCESS, save=False)
        job.finished_at = datetime.datetime.now()
        job.save()


class DataStorageSyncJob(JobType):
    name = "Data storage sync"
    key = "data_storage_sync"

    @classmethod
    def run(cls, job: "Job"):
        """
        Run the data storage sync job.

        This is meant to be called by an async task, not directly.
        """

        job.progress.add_stage(cls.name)
        job.progress.add_stage_param(cls.key, "Total files", 0)
        job.progress.add_stage_param(cls.key, "Failed", 0)
        job.update_status(JobState.STARTED)
        job.started_at = datetime.datetime.now()
        job.finished_at = None
        job.save()

        if not job.deployment:
            raise ValueError("No deployment provided for data storage sync job")
        else:
            job.logger.info(f"Syncing captures for deployment {job.deployment}")
            job.progress.update_stage(
                cls.key,
                status=JobState.STARTED,
                progress=0,
                total_files=0,
            )
            job.save()

            job.deployment.sync_captures(job=job)

            job.logger.info(f"Finished syncing captures for deployment {job.deployment}")
            job.progress.update_stage(
                cls.key,
                status=JobState.SUCCESS,
                progress=1,
            )
            job.update_status(JobState.SUCCESS)
            job.save()

        job.finished_at = datetime.datetime.now()
        job.save()


class SourceImageCollectionPopulateJob(JobType):
    name = "Populate captures collection"
    key = "populate_captures_collection"

    @classmethod
    def run(cls, job: "Job"):
        """
        Run the populate source image collection job.

        This is meant to be called by an async task, not directly.
        """
        job.progress.add_stage(cls.name, key=cls.key)
        job.progress.add_stage_param(cls.key, "Captures added", "")
        job.update_status(JobState.STARTED)
        job.started_at = datetime.datetime.now()
        job.finished_at = None
        job.save()

        if not job.source_image_collection:
            raise ValueError("No source image collection provided")

        job.logger.info(f"Populating source image collection {job.source_image_collection}")
        job.update_status(JobState.STARTED)
        job.started_at = datetime.datetime.now()
        job.finished_at = None
        job.progress.update_stage(
            cls.key,
            status=JobState.STARTED,
            progress=0.10,
            captures_added=0,
        )
        job.save()

        job.source_image_collection.populate_sample(job=job)
        job.logger.info(f"Finished populating source image collection {job.source_image_collection}")
        job.save()

        captures_added = job.source_image_collection.images.count()
        job.logger.info(f"Added {captures_added} captures to source image collection {job.source_image_collection}")

        job.progress.update_stage(
            cls.key,
            status=JobState.SUCCESS,
            progress=1,
            captures_added=captures_added,
        )
        job.finished_at = datetime.datetime.now()
        job.update_status(JobState.SUCCESS, save=False)
        job.save()


class DataExportJob(JobType):
    """
    Job type to handle Project data exports
    """

    name = "Data Export"
    key = "data_export"

    @classmethod
    def run(cls, job: "Job"):
        """
        Run the export job asynchronously with format selection (CSV, JSON, Darwin Core).
        """
        logger.info("Job started: Exporting occurrences")

        # Add progress tracking
        job.progress.add_stage("Exporting data", cls.key)
        job.update_status(JobState.STARTED)
        job.started_at = datetime.datetime.now()
        job.finished_at = None
        job.save()

        job.logger.info(f"Starting export for project {job.project}")

        file_url = job.data_export.run_export()

        job.logger.info(f"Export completed: {file_url}")
        job.logger.info(f"File uploaded to Project Storage: {file_url}")
        # Finalize Job
        stage = job.progress.add_stage("Uploading snapshot")
        job.progress.add_stage_param(stage.key, "File URL", f"{file_url}")
        job.progress.update_stage(stage.key, status=JobState.SUCCESS, progress=1)
        job.finished_at = datetime.datetime.now()
        job.update_status(JobState.SUCCESS, save=True)


class PostProcessingJob(JobType):
    name = "Post Processing"
    key = "post_processing"

    @classmethod
    def run(cls, job: "Job"):
        job.progress.add_stage(cls.name, key=cls.key)
        job.update_status(JobState.STARTED)
        job.started_at = datetime.datetime.now()
        job.save()

        params = job.params or {}
        task_key: str = params.get("task", "")
        config = params.get("config", {})
        job.logger.info(f"Post-processing task: {task_key} with params: {job.params}")

        task_cls = get_postprocessing_task(key=task_key)
        if not task_cls:
            raise ValueError(f"Unknown post-processing task '{task_key}'")

        task = task_cls(job=job, **config)
        task.run()
        job.progress.update_stage(cls.key, status=JobState.SUCCESS, progress=1)
        job.finished_at = datetime.datetime.now()
        job.update_status(JobState.SUCCESS)
        job.save()


class UnknownJobType(JobType):
    name = "Unknown"
    key = "unknown"

    @classmethod
    def run(cls, job: "Job"):
        raise ValueError(f"Unknown job type '{job.job_type()}'")


VALID_JOB_TYPES = [
    MLJob,
    SourceImageCollectionPopulateJob,
    DataStorageSyncJob,
    UnknownJobType,
    DataExportJob,
    PostProcessingJob,
]


def get_job_type_by_key(key: str) -> type[JobType] | None:
    for job_type in VALID_JOB_TYPES:
        if job_type.key == key:
            return job_type


def get_job_type_by_inferred_key(job: "Job") -> type[JobType] | None:
    """
    Infer the job type from the job's attributes.

    This is used for a data migration to set the job type of existing jobs
    before the job type field was added to the model.
    """

    if job.pipeline:
        return MLJob
    # Check the key of the first stage in the job progress
    if job.progress.stages:
        job_type = get_job_type_by_key(job.progress.stages[0].key)
        if job_type:
            return job_type


class Job(BaseModel):
    """A job to be run by the scheduler"""

    # Hide old failed jobs after 3 days
    FAILED_CUTOFF_HOURS = 24 * 3

    name = models.CharField(max_length=255)
    queue = models.CharField(max_length=255, default="default")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # @TODO can we use an Enum or Pydantic model for status?
    status = models.CharField(max_length=255, default=JobState.CREATED.name, choices=JobState.choices())
    progress: JobProgress = SchemaField(JobProgress, default=default_job_progress)
    logs: JobLogs = SchemaField(JobLogs, default=JobLogs)
    params = models.JSONField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    delay = models.IntegerField("Delay in seconds", default=0, help_text="Delay before running the job")
    limit = models.IntegerField(
        "Limit", null=True, blank=True, default=None, help_text="Limit the number of images to process"
    )
    shuffle = models.BooleanField("Shuffle", default=True, help_text="Process images in a random order")
    job_type_key = models.CharField(
        "Job Type", max_length=255, default=UnknownJobType.key, choices=[(t.key, t.name) for t in VALID_JOB_TYPES]
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    deployment = models.ForeignKey(
        Deployment,
        on_delete=models.CASCADE,
        related_name="jobs",
        null=True,
        blank=True,
    )
    source_image_single = models.ForeignKey(
        SourceImage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
    source_image_collection = models.ForeignKey(
        SourceImageCollection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
    data_export = models.OneToOneField(
        "exports.DataExport",
        on_delete=models.CASCADE,  # If DataExport is deleted, delete the Job
        null=True,
        blank=True,
        related_name="job",
    )
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
    dispatch_mode = models.CharField(
        max_length=32,
        choices=JobDispatchMode.choices,
        default=JobDispatchMode.INTERNAL,
        help_text="How the job dispatches its workload: internal, sync_api, or async_api.",
    )

    def __str__(self) -> str:
        return f'#{self.pk} "{self.name}" ({self.status})'

    def job_type(self) -> type[JobType]:
        job_type_class = get_job_type_by_key(self.job_type_key)
        if job_type_class:
            return job_type_class
        else:
            inferred_job_type = get_job_type_by_inferred_key(self)
            msg = f"Could not determine job type for job {self.pk} with job_type_key '{self.job_type_key}'. "
            if inferred_job_type:
                msg += f"Inferred job type as '{inferred_job_type.name}'"
            raise ValueError(msg)

    def enqueue(self):
        """
        Add the job to the queue so that it will run in the background.
        """
        assert self.pk is not None, "Job must be saved before it can be enqueued"
        task_id = uuid()

        def send_task():
            run_job.apply_async(kwargs={"job_id": self.pk}, task_id=task_id)

        transaction.on_commit(send_task)
        self.task_id = task_id
        self.started_at = None
        self.finished_at = None
        self.scheduled_at = datetime.datetime.now()
        self.status = AsyncResult(task_id).status
        self.update_progress(save=False)
        self.save()

    def setup(self, save=True):
        """
        Setup the job by creating the job stages.
        """
        self.progress = self.progress or self.get_default_progress()

        if self.delay:
            delay_stage = self.progress.add_stage("Delay")
            self.progress.add_stage_param(delay_stage.key, "Delay", self.delay)
            self.progress.add_stage_param(delay_stage.key, "Mood", "😴")

        if self.pipeline:
            # Set dispatch mode based on project feature flags at creation time
            # so the UI can show the correct mode before the job runs.
            # Only override if still at the default (INTERNAL), to allow explicit overrides.
            if self.dispatch_mode == JobDispatchMode.INTERNAL:
                if self.project and self.project.feature_flags.async_pipeline_workers:
                    self.dispatch_mode = JobDispatchMode.ASYNC_API
                else:
                    self.dispatch_mode = JobDispatchMode.SYNC_API

            collect_stage = self.progress.add_stage("Collect")
            self.progress.add_stage_param(collect_stage.key, "Total Images", "")

            pipeline_stage = self.progress.add_stage("Process")
            self.progress.add_stage_param(pipeline_stage.key, "Processed", "")
            self.progress.add_stage_param(pipeline_stage.key, "Remaining", "")
            self.progress.add_stage_param(pipeline_stage.key, "Failed", "")

            saving_stage = self.progress.add_stage("Results")
            self.progress.add_stage_param(saving_stage.key, "Captures", "")
            self.progress.add_stage_param(saving_stage.key, "Detections", "")
            self.progress.add_stage_param(saving_stage.key, "Classifications", "")

        if save:
            self.save()

    def run(self):
        """
        Run the job.

        This is meant to be called by an async task, not directly.
        """
        job_type = self.job_type()
        job_type.run(job=self)
        return None

    def retry(self, async_task=True):
        """
        Retry the job.
        """
        self.logger.info(f"Re-running job {self}")
        self.finished_at = None
        self.progress.reset()
        self.status = JobState.RETRY
        self.save()
        if async_task:
            self.enqueue()
        else:
            self.run()

    def cancel(self):
        """
        Terminate the celery task.
        """
        self.status = JobState.CANCELING
        self.save()
        if self.task_id:
            task = run_job.AsyncResult(self.task_id)
            if task:
                task.revoke(terminate=True)
                self.save()
        else:
            self.status = JobState.REVOKED
            self.save()

    def update_status(self, status=None, save=True):
        """
        Update the status of the job based on the status of the celery task.
        Or if a status is provided, update the status of the job to that value.
        """
        if not status and self.task_id:
            task = run_job.AsyncResult(self.task_id)
            status = task.status

        if not status:
            self.logger.warning(f"Could not determine status of job {self.pk}")
            return

        if status != self.status:
            self.logger.info(f"Changing status of job {self.pk} from {self.status} to {status}")
            self.status = status

        self.progress.summary.status = status

        if save:
            self.save()

    def update_progress(self, save=True):
        """
        Update the total aggregate progress from the progress of each stage.
        """
        if not len(self.progress.stages):
            # Need at least one stage to calculate progress
            total_progress = 0
        else:
            for stage in self.progress.stages:
                if stage.progress > 0 and stage.status == JobState.CREATED:
                    # Update any stages that have started but are still in the CREATED state
                    stage.status = JobState.STARTED
                elif stage.status in JobState.final_states() and stage.progress < 1:
                    # Update any stages that are complete but have a progress less than 1
                    stage.progress = 1
                elif stage.progress == 1 and stage.status not in JobState.final_states():
                    # Update any stages that are complete but are still in the STARTED state
                    stage.status = JobState.SUCCESS
            total_progress = sum([stage.progress for stage in self.progress.stages]) / len(self.progress.stages)

        self.progress.summary.progress = total_progress

        if save:
            self.save(update_progress=False)

    def duration(self) -> datetime.timedelta | None:
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None

    def save(self, update_progress=True, *args, **kwargs):
        """
        Create the job stages if they don't exist.
        """
        if self.pk and self.progress.stages and update_progress:
            self.update_progress(save=False)
        else:
            self.setup(save=False)
        super().save(*args, **kwargs)
        logger.debug(f"Saved job {self}")
        if self.progress.summary.status != self.status:
            logger.warning(f"Job {self} status mismatches progress: {self.progress.summary.status} != {self.status}")

    def check_custom_permission(self, user, action: str) -> bool:
        job_type = self.job_type_key.lower()
        if self.source_image_single:
            action = "run_single_image"
        if action in ["run", "cancel", "retry"]:
            permission_codename = f"run_{job_type}_job"
        else:
            permission_codename = f"{action}_{job_type}_job"

        project = self.get_project() if hasattr(self, "get_project") else None
        return user.has_perm(permission_codename, project)

    def get_custom_user_permissions(self, user) -> list[str]:
        project = self.get_project()
        if not project:
            return []

        custom_perms = set()
        model_name = "job"
        perms = get_perms(user, project)
        job_type = self.job_type_key.lower()
        for perm in perms:
            # permissions are in the format "action_modelname"
            if perm.endswith(f"{job_type}_{model_name}"):
                action = perm[: -len(f"_{job_type}_{model_name}")]
                # make sure to exclude standard CRUD actions
                if action not in ["view", "create", "update", "delete"]:
                    custom_perms.add(action)
        logger.debug(f"Custom permissions for user {user} on project {self}, with jobtype {job_type}: {custom_perms}")
        return list(custom_perms)

    @classmethod
    def get_default_progress(cls) -> JobProgress:
        """Return the progress of each stage of this job as a dictionary"""
        return default_job_progress()

    @property
    def logger(self) -> logging.Logger:
        _logger = logging.getLogger(f"ami.jobs.{self.pk}")

        # Only add JobLogHandler if not already present
        if not any(isinstance(h, JobLogHandler) for h in _logger.handlers):
            # Also log output to a field on thie model instance
            logger.info("Adding JobLogHandler to logger for job %s", self.pk)
            _logger.addHandler(JobLogHandler(self))
        _logger.propagate = False
        return _logger

    class Meta:
        ordering = ["-created_at"]
        # permissions = [
        #     ("run_job", "Can run a job"),
        #     ("cancel_job", "Can cancel a job"),
