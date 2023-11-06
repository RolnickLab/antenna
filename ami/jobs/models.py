import datetime
import logging
import time

import pydantic
from django.db import models
from django.utils.text import slugify
from django_pydantic_field import SchemaField

import ami.tasks
from ami.main.models import BaseModel, Deployment, Pipeline, Project, SourceImage, SourceImageCollection
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
    REVOKED = "REVOKED"
    RECEIVED = "RECEIVED"


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


class JobProgressSummary(pydantic.BaseModel):
    """Summary of all stages of a job"""

    status: JobState = JobState.CREATED
    progress: float = 0
    status_label: str = ""

    @pydantic.validator("status_label", always=True)
    def serialize_status_label(cls, value, values) -> str:
        return get_status_label(values["status"], values["progress"])

    class Config:
        use_enum_values = True


class JobProgressStageDetail(JobProgressSummary):
    """A stage of a job"""

    key: str
    name: str
    time_elapsed: datetime.timedelta = datetime.timedelta()
    time_remaining: datetime.timedelta | None = None
    input_size: int = 0
    output_size: int = 0


stage_parameters = JobProgressStageDetail.__fields__.keys()


class JobProgress(pydantic.BaseModel):
    """The full progress of a job and its stages."""

    summary: JobProgressSummary
    stages: list[JobProgressStageDetail]

    def add_stage(self, name: str) -> JobProgressStageDetail:
        stage = JobProgressStageDetail(
            key=slugify(name),
            name=name,
        )
        self.stages.append(stage)
        return stage

    def update_stage(self, stage_key: str, **stage_parameters) -> JobProgressStageDetail | None:
        stage_keys = [stage.key for stage in self.stages]
        if stage_key not in stage_keys:
            raise ValueError(f"Job stage with key '{stage_key}' not found in progress")

        for stage in self.stages:
            if stage.key == stage_key:
                for k, v in stage_parameters.items():
                    setattr(stage, k, v)
                return stage

    class Config:
        use_enum_values = True
        as_dict = True


default_job_progress = JobProgress(
    summary=JobProgressSummary(status=JobState.CREATED, progress=0),
    stages=[],
)

default_ml_job_progress = JobProgress(
    summary=JobProgressSummary(status=JobState.CREATED, progress=0),
    stages=[
        JobProgressStageDetail(
            key="object_detection",
            name="Object Detection",
            status=JobState.CREATED,
            progress=0,
            time_elapsed=datetime.timedelta(),
            time_remaining=None,
            input_size=0,
            output_size=0,
        ),
        JobProgressStageDetail(
            key="binary_classification",
            name="Objects of Interest Filter",
            status=JobState.CREATED,
            progress=0,
            time_elapsed=datetime.timedelta(),
            time_remaining=None,
            input_size=0,
            output_size=0,
        ),
        JobProgressStageDetail(
            key="species_classification",
            name="Species Classification",
            status=JobState.CREATED,
            progress=0,
            time_elapsed=datetime.timedelta(),
            time_remaining=None,
            input_size=0,
            output_size=0,
        ),
        JobProgressStageDetail(
            key="tracking",
            name="Occurrence Tracking",
            status=JobState.CREATED,
            progress=0,
            time_elapsed=datetime.timedelta(),
            time_remaining=None,
            input_size=0,
            output_size=0,
        ),
    ],
)


default_job_config = {
    "input": {
        "name": "N/A",
        "size": 0,
    },
    "stages": [
        {
            "name": "Delay",
            "key": "delay",
            "params": [
                {"key": "delay_seconds", "name": "Delay seconds", "value": "N/A"},
            ],
        },
    ],
}

default_ml_job_config = {
    "input": {
        "name": "Captures",
        "size": 100,
    },
    "stages": [
        {
            "name": "Object Detection",
            "key": "object_detection",
            "params": [
                {"key": "model", "name": "Localization Model", "value": "yolov5s"},
                {"key": "batch_size", "name": "Batch size", "value": 8},
                # {"key": "threshold", "name": "Threshold", "value": 0.5},
                {"key": "input_size", "name": "Images processed", "read_only": True},
                {"key": "output_size", "name": "Objects detected", "read_only": True},
            ],
        },
        {
            "name": "Objects of Interest Filter",
            "key": "binary_classification",
            "params": [
                {"key": "algorithm", "name": "Binary classification model", "value": "resnet18"},
                {"key": "batch_size", "name": "Batch size", "value": 8},
                {"key": "input_size", "name": "Objects processed", "read_only": True},
                {"key": "output_size", "name": "Objects of interest", "read_only": True},
            ],
        },
        {
            "name": "Species Classification",
            "key": "species_classification",
            "params": [
                {"key": "algorithm", "name": "Species classification model", "value": "resnet18"},
                {"key": "batch_size", "name": "Batch size", "value": 8},
                {"key": "threshold", "name": "Confidence threshold", "value": 0.5},
                {"key": "input_size", "name": "Species processed", "read_only": True},
                {"key": "output_size", "name": "Species classified", "read_only": True},
            ],
        },
        {
            "name": "Occurrence Tracking",
            "key": "tracking",
            "params": [
                {"key": "algorithm", "name": "Occurrence tracking algorithm", "value": "adityacombo"},
                {"key": "input_size", "name": "Detections processed", "read_only": True},
                {"key": "output_size", "name": "Occurrences identified", "read_only": True},
            ],
        },
    ],
}

example_non_model_config = {
    "input": {
        "name": "Raw Captures",
        "source": "s3://bucket/path/to/captures",
        "size": 100,
    },
    "stages": [
        {
            "name": "Image indexing",
            "key": "image_indexing",
            "params": [
                {"key": "input_size", "name": "Directories scanned", "read_only": True},
                {"key": "output_size", "name": "Images indexed", "read_only": True},
            ],
        },
        {
            "name": "Image resizing",
            "key": "image_resizing",
            "params": [
                {"key": "width", "name": "Width", "value": 640},
                {"key": "height", "name": "Height", "value": 480},
                {"key": "input_size", "name": "Images processed", "read_only": True},
            ],
        },
        {
            "name": "Feature extraction",
            "key": "feature_extraction",
            "params": [
                {"key": "algorithm", "name": "Feature extractor", "value": "imagenet"},
                {"key": "input_size", "name": "Images processed", "read_only": True},
            ],
        },
    ],
}


class Job(BaseModel):
    """A job to be run by the scheduler

    Example config:
    """

    name = models.CharField(max_length=255)
    config = models.JSONField(default=default_job_config, null=True, blank=False)
    queue = models.CharField(max_length=255, default="default")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # @TODO can we use an Enum or Pydantic model for status?
    status = models.CharField(max_length=255, default=JobState.CREATED.name, choices=JobState.choices())
    progress: JobProgress = SchemaField(JobProgress, default=default_job_progress)
    result = models.JSONField(null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    delay = models.IntegerField("Delay in seconds", default=0, help_text="Delay before running the job")

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
        return f"{self.name} ({self.status})"

    def enqueue(self):
        """
        Add the job to the queue so that it will run in the background.
        """
        # ami.tasks.run_job.delay(self.pk)
        # task_id = ami.tasks.run_job.apply_async(args=[self.pk], queue=self.queue).id
        task_id = ami.tasks.run_job.apply_async(kwargs={"job_id": self.pk}).id
        self.task_id = task_id
        self.started_at = None
        self.finished_at = None
        self.scheduled_at = datetime.datetime.now()
        self.status = ami.tasks.run_job.AsyncResult(task_id).status
        self.save()

    def setup(self, save=True):
        """
        Setup the job by creating the job stages.
        """
        self.progress = self.progress or default_job_progress

        if self.delay:
            self.progress.add_stage("Delay")

        if save:
            self.save()

    def run(self):
        """
        Run the job.

        This is meant to be called by an async task, not directly.
        """

        self.update_status(JobState.STARTED)
        self.started_at = datetime.datetime.now()
        self.finished_at = None
        self.save()

        if self.delay:
            for i in range(self.delay):
                logger.info(f"Delaying job {self.pk} for {i} out of {self.delay} seconds")
                time.sleep(1)
                self.progress.update_stage(
                    "delay",
                    status=JobState.STARTED,
                    progress=i / self.delay,
                )
                self.save()
            self.progress.update_stage("delay", status=JobState.SUCCESS, progress=1)
            self.save()

        self.update_status(JobState.SUCCESS)
        self.finished_at = datetime.datetime.now()
        self.save()

    def cancel(self):
        """
        Terminate the celery task.
        """
        if self.task_id:
            task = ami.tasks.run_job.AsyncResult(self.task_id)
            if task:
                task.revoke(terminate=True)
                self.status = task.status
                self.save()

    def update_status(self, status=None, save=True):
        """
        Update the status of the job based on the status of the celery task.
        Or if a status is provided, update the status of the job to that value.
        """
        if not status and self.task_id:
            task = ami.tasks.run_job.AsyncResult(self.task_id)
            status = task.status

        if not status:
            logger.warn(f"Could not determine status of job {self.pk}")
            return

        self.status = status
        self.progress.summary.status = status

        if save:
            self.save()

    def update_progress(self, save=True):
        """
        Update the total aggregate progress from the progress of each stage.
        """
        if not len(self.progress.stages):
            total_progress = 0
        else:
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
    def default_config(cls) -> dict:
        return default_job_config

    @classmethod
    def default_progress(cls) -> JobProgress:
        """Return the progress of each stage of this job as a dictionary"""
        return default_job_progress
