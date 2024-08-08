import datetime
import logging
import random
import time
import typing
from dataclasses import dataclass

import pydantic
from django.db import models
from django.utils.text import slugify
from django_pydantic_field import SchemaField

from ami.base.models import BaseModel
from ami.base.schemas import ConfigurableStage, ConfigurableStageParam
from ami.jobs.tasks import run_job
from ami.main.models import Deployment, Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.utils.schemas import OrderedEnum

logger = logging.getLogger(__name__)


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
    """Summary of all stages of a job"""

    status: JobState = JobState.CREATED
    progress: float = 0
    status_label: str = ""

    @pydantic.validator("status_label", always=True)
    def serialize_status_label(cls, value, values) -> str:
        if "status" not in values or "progress" not in values:
            # Does this happen if status label gets initialized before status and progress?
            return ""
        return get_status_label(values["status"], values["progress"])

    class Config:
        use_enum_values = True


class JobProgressStageDetail(ConfigurableStage, JobProgressSummary):
    """A stage of a job"""

    pass


stage_parameters = JobProgressStageDetail.__fields__.keys()


class JobProgress(pydantic.BaseModel):
    """The full progress of a job and its stages."""

    summary: JobProgressSummary
    stages: list[JobProgressStageDetail]
    errors: list[str] = []
    logs: list[str] = []

    def get_stage_key(self, name: str) -> str:
        return python_slugify(name)

    def add_stage(self, name: str) -> JobProgressStageDetail:
        key = self.get_stage_key(name)
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
                if stage.name == stage.key:
                    raise ValueError(f"Job stage with key '{stage_key}' has no name")
                return stage
        raise ValueError(f"Job stage with key '{stage_key}' not found in progress")

    def get_stage_param(self, stage_key: str, param_key: str) -> ConfigurableStageParam:
        stage = self.get_stage(stage_key)
        for param in stage.params:
            if param.key == param_key:
                return param
        raise ValueError(f"Job stage parameter with key '{param_key}' not found in stage '{stage_key}'")

    def add_stage_param(self, stage_key: str, name: str, value: typing.Any = None) -> ConfigurableStageParam:
        stage = self.get_stage(stage_key)
        try:
            return self.get_stage_param(stage_key, self.get_stage_key(name))
        except ValueError:
            param = ConfigurableStageParam(
                name=name,
                key=self.get_stage_key(name),
                value=value,
            )
            stage.params.append(param)
            return param

    def add_or_update_stage_param(self, stage_key: str, name: str, value: typing.Any = None) -> ConfigurableStageParam:
        try:
            param = self.get_stage_param(stage_key, self.get_stage_key(name))
            param.value = value
            return param
        except ValueError:
            return self.add_stage_param(stage_key, name, value)

    def update_stage(self, stage_key_or_name: str, **stage_parameters) -> JobProgressStageDetail | None:
        """ "
        Update the parameters of a stage of the job.

        Will update parameters that are direct attributes of the stage,
        or parameters that are in the stage's params list.

        This is the preferred method to update a stage's parameters.
        """
        stage_key = self.get_stage_key(stage_key_or_name)  # Allow both title or key to be used for lookup
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

    class Config:
        use_enum_values = True
        as_dict = True


def default_job_progress() -> JobProgress:
    return JobProgress(
        summary=JobProgressSummary(status=JobState.CREATED, progress=0),
        stages=[],
    )


def default_ml_job_progress() -> JobProgress:
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


class JobLogHandler(logging.Handler):
    """
    Class for handling logs from a job and writing them to the job instance.
    """

    max_log_length = 1000

    def __init__(self, job: "Job", *args, **kwargs):
        self.job = job
        super().__init__(*args, **kwargs)

    def emit(self, record):
        # Log to the current app logger
        logger.log(record.levelno, self.format(record))

        # Write to the logs field on the job instance
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{timestamp}] {record.levelname} {self.format(record)}"
        if msg not in self.job.progress.logs:
            self.job.progress.logs.insert(0, msg)

        # Write a simpler copy of any errors to the errors field
        if record.levelno >= logging.ERROR:
            if record.message not in self.job.progress.errors:
                self.job.progress.errors.insert(0, record.message)

        if len(self.job.progress.logs) > self.max_log_length:
            self.job.progress.logs = self.job.progress.logs[: self.max_log_length]
        self.job.save()


@dataclass
class JobType:
    name: str
    key: str

    @classmethod
    def run(cls, job: "Job"):
        """
        Execute the run function specific to this job type.
        """
        pass


AnyJobType = typing.TypeVar("AnyJobType", bound=JobType)


class MLJob(JobType):
    name = "ML pipeline"
    key = "ml"

    @classmethod
    def run(cls, job: "Job"):
        """
        Procedure for an ML pipeline as a job.
        """
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

        if job.pipeline:
            job.progress.update_stage(
                "collect",
                status=JobState.STARTED,
                progress=0,
            )

            images = list(
                # @TODO return generator plus image count
                # @TODO pass to celery group chain?
                job.pipeline.collect_images(
                    collection=job.source_image_collection,
                    deployment=job.deployment,
                    source_images=[job.source_image_single] if job.source_image_single else None,
                    job_id=job.pk,
                    skip_processed=True,
                    # shuffle=job.shuffle,
                )
            )
            source_image_count = len(images)
            job.progress.update_stage("collect", total_images=source_image_count)

            if job.shuffle and source_image_count > 1:
                job.logger.info("Shuffling images")
                random.shuffle(images)

            # @TODO remove this temporary limit
            TEMPORARY_LIMIT = 1000
            job.limit = job.limit or TEMPORARY_LIMIT

            if job.limit and source_image_count > job.limit:
                job.logger.warn(f"Limiting number of images to {job.limit} (out of {source_image_count})")
                images = images[: job.limit]
                image_count = len(images)
                job.progress.add_stage_param("collect", "Limit", image_count)
            else:
                image_count = source_image_count

            job.progress.update_stage(
                "collect",
                status=JobState.SUCCESS,
                progress=1,
            )

            total_detections = 0
            total_classifications = 0

            CHUNK_SIZE = 4  # Keep it low to see more progress updates
            chunks = [images[i : i + CHUNK_SIZE] for i in range(0, image_count, CHUNK_SIZE)]  # noqa

            for i, chunk in enumerate(chunks):
                try:
                    results = job.pipeline.process_images(
                        images=chunk,
                        job_id=job.pk,
                    )
                except Exception as e:
                    # Log error about image batch and continue
                    job.logger.error(f"Failed to process image batch {i} of {len(chunks)}: {e}")
                    continue

                total_detections += len(results.detections)
                total_classifications += len([c for d in results.detections for c in d.classifications])
                job.progress.update_stage(
                    "process",
                    status=JobState.STARTED,
                    progress=(i + 1) / len(chunks),
                    processed=(i + 1) * CHUNK_SIZE,
                    remaining=image_count - (i + 1) * CHUNK_SIZE,
                    detections=total_detections,
                    classifications=total_classifications,
                )
                job.save()
                objects = job.pipeline.save_results(results=results, job_id=job.pk)
                job.progress.update_stage(
                    "results",
                    status=JobState.STARTED,
                    progress=(i + 1) / len(chunks),
                    objects_created=len(objects),
                )
                job.update_progress()
                job.save()

            job.progress.update_stage(
                "process",
                status=JobState.SUCCESS,
            )
            job.progress.update_stage(
                "results",
                status=JobState.SUCCESS,
            )

        job.update_status(JobState.SUCCESS)
        job.update_progress()
        job.finished_at = datetime.datetime.now()
        job.save()


class DataStorageSyncJob(JobType):
    name = "Data storage sync"
    key = "data_storage_sync"

    @classmethod
    def setup(cls, job: "Job", save=True):
        job.progress = job.progress or default_job_progress
        job.progress.add_stage(name=cls.name)

        if save:
            job.save()

    @classmethod
    def run(cls, job: "Job"):
        """
        Run the data storage sync job.

        This is meant to be called by an async task, not directly.
        """

        job.progress.add_stage_param(cls.key, "Total Files", "")
        job.update_status(JobState.STARTED)
        job.started_at = datetime.datetime.now()
        job.finished_at = None
        job.save()

        if job.deployment:
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
        else:
            job.update_status(JobState.FAILURE)

        job.update_progress()
        job.finished_at = datetime.datetime.now()
        job.save()


class UnknownJobType(JobType):
    name = "Unknown"
    key = "unknown"

    @classmethod
    def run(cls, job: "Job"):
        job.logger.error(f"Unknown job type '{job.job_type()}'")
        job.update_status(JobState.UNKNOWN)
        job.save()


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
    progress: JobProgress = SchemaField(JobProgress, default=default_job_progress())
    result = models.JSONField(null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    delay = models.IntegerField("Delay in seconds", default=0, help_text="Delay before running the job")
    limit = models.IntegerField(
        "Limit", null=True, blank=True, default=1000, help_text="Limit the number of images to process"
    )
    shuffle = models.BooleanField("Shuffle", default=True, help_text="Process images in a random order")

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
    pipeline = models.ForeignKey(
        Pipeline,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )

    def __str__(self) -> str:
        return f'#{self.pk} "{self.name}" ({self.status})'

    def job_type(self) -> type[JobType]:
        """
        This is a temporary way to determine the type of job.
        @TODO rework Job classes and background tasks.
        """
        if self.pipeline:
            return MLJob

        try:
            self.progress.get_stage(DataStorageSyncJob.key)
            return DataStorageSyncJob
        except ValueError:
            pass

        return UnknownJobType

    def enqueue(self):
        """
        Add the job to the queue so that it will run in the background.
        """
        assert self.pk is not None, "Job must be saved before it can be enqueued"
        task_id = run_job.apply_async(kwargs={"job_id": self.pk}).id
        self.task_id = task_id
        self.started_at = None
        self.finished_at = None
        self.scheduled_at = datetime.datetime.now()
        self.status = run_job.AsyncResult(task_id).status
        self.update_progress(save=False)
        self.save()

    def setup(self, save=True):
        """
        Setup the job by creating the job stages.
        """
        self.progress = self.progress or default_job_progress

        if self.delay:
            delay_stage = self.progress.add_stage("Delay")
            self.progress.add_stage_param(delay_stage.key, "Delay", self.delay)
            self.progress.add_stage_param(delay_stage.key, "Mood", "😴")

        if self.pipeline:
            collect_stage = self.progress.add_stage("Collect")
            self.progress.add_stage_param(collect_stage.key, "Total Images", "")

            pipeline_stage = self.progress.add_stage("Process")
            self.progress.add_stage_param(pipeline_stage.key, "Processed", "")
            self.progress.add_stage_param(pipeline_stage.key, "Remaining", "")
            self.progress.add_stage_param(pipeline_stage.key, "Detections", "")
            self.progress.add_stage_param(pipeline_stage.key, "Classifications", "")

            saving_stage = self.progress.add_stage("Results")
            self.progress.add_stage_param(saving_stage.key, "Objects created", "")

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
                self.status = task.status
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
            self.logger.warn(f"Could not determine status of job {self.pk}")
            return

        if status != self.status:
            self.logger.info(f"Changing status of job {self.pk} to {status}")
            self.status = status

        self.progress.summary.status = status

        if save:
            self.save()

    def update_progress(self, save=True):
        """
        Update the total aggregate progress from the progress of each stage.
        """
        if not len(self.progress.stages):
            total_progress = 1
        else:
            for stage in self.progress.stages:
                if stage.progress > 0 and stage.status == JobState.CREATED:
                    # Update any stages that have started but are still in the CREATED state
                    stage.status = JobState.STARTED
                elif stage.status == JobState.SUCCESS and stage.progress < 1:
                    # Update any stages that are complete but have a progress less than 1
                    stage.progress = 1
                elif stage.progress == 1 and stage.status == JobState.STARTED:
                    # Update any stages that are complete but are still in the STARTED state
                    stage.status = JobState.SUCCESS
            total_progress = sum([stage.progress for stage in self.progress.stages]) / len(self.progress.stages)

        self.progress.summary.progress = total_progress

        if save:
            self.save()

    def duration(self) -> datetime.timedelta | None:
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None

    def save(self, *args, **kwargs):
        """
        Create the job stages if they don't exist.
        """
        if self.progress.stages:
            self.update_progress(save=False)
        else:
            self.setup(save=False)
        super().save(*args, **kwargs)

    @classmethod
    def default_progress(cls) -> JobProgress:
        """Return the progress of each stage of this job as a dictionary"""
        return default_job_progress()

    @property
    def logger(self) -> logging.Logger:
        logger = logging.getLogger(f"ami.jobs.{self.pk}")
        # Also log output to a field on thie model instance
        logger.addHandler(JobLogHandler(self))
        return logger

    class Meta:
        ordering = ["-created_at"]
        # permissions = [
        #     ("run_job", "Can run a job"),
        #     ("cancel_job", "Can cancel a job"),
        # ]
