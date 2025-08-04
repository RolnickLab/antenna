import datetime
import json
import logging
import random
import time
import typing
from dataclasses import dataclass

import pydantic
from celery import uuid
from celery.result import AsyncResult
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils.text import slugify
from django_pydantic_field import SchemaField

from ami.base.models import BaseModel
from ami.base.schemas import ConfigurableStage, ConfigurableStageParam
from ami.jobs.tasks import run_job
from ami.main.models import Deployment, Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.schemas import PipelineRequest, PipelineResultsResponse
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
    """The full progress of a job and its stages."""

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
    def check_inprogress_subtasks(cls, job: "Job") -> bool | None:
        """
        Check on the status of inprogress subtasks and update the job progress accordingly.
        """
        pass

    @classmethod
    def run(cls, job: "Job"):
        """
        Execute the run function specific to this job type.
        """
        raise NotImplementedError("Job type has not implemented the run method")


class MLJob(JobType):
    name = "ML pipeline"
    key = "ml"

    @staticmethod
    def schedule_check_ml_job_status(ml_job_id: str):
        """Schedule a periodic task to check the status of the MLJob's subtasks."""
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        schedule, _ = IntervalSchedule.objects.get_or_create(
            # @TODO: env variable depending on prod/dev
            # or based on how many source images are being processed
            every=15,
            period=IntervalSchedule.SECONDS,
        )
        beat_task_name = f"check_ml_job_status_{ml_job_id}"
        PeriodicTask.objects.create(
            interval=schedule,
            name=beat_task_name,
            task="ami.ml.tasks.check_ml_job_status",
            args=json.dumps([ml_job_id]),
        )

    @classmethod
    def check_inprogress_subtasks(cls, job: "Job") -> bool:
        """
        Check the status of the MLJob subtasks and update the job progress accordingly.
        Returns True if all subtasks are completed.
        """
        if not job.inprogress_subtasks:
            cls.update_job_progress(job)
            return True

        subtasks = job.subtasks or []
        subtasks_inprogress = []
        for inprogress_subtask in job.inprogress_subtasks:
            subtask = Subtask(**inprogress_subtask)
            task_name = subtask.task_name
            task_id = subtask.task_id

            ml_task_record = job.ml_task_records.filter(task_id=task_id).first()
            if not ml_task_record:
                raise Exception(
                    f"MLTaskRecord for job {job.pk} with task ID {task_id} and task name {task_name} not found"
                )

            task = AsyncResult(task_id)
            if task.ready():
                if task.successful():
                    job.logger.info(f"Sub-task {task_name} {task_id} completed successfully")
                else:
                    job.logger.error(f"Sub-task {task_name} {task_id} failed: {task.result}")

                results_dict = task.result
                if (
                    task_name == "process_pipeline_request"
                ):  # NOTE: results backend doesn't allow storing task name, so I saved it to the job instead
                    results = PipelineResultsResponse(**results_dict)  # type: ignore
                    num_captures = len(results.source_images)
                    num_detections = len(results.detections)
                    num_classifications = len([c for d in results.detections for c in d.classifications])
                    if results.source_images or results.detections:
                        task_result = job.pipeline.save_results_async(results=results, job_id=job.pk)
                        # Create a new MLTaskRecord for save_results
                        save_results_task_record = MLTaskRecord.objects.create(
                            job=job,
                            task_id=task_result.id,
                            task_name="save_results",
                            pipeline_response=results,
                            num_captures=num_captures,
                            num_detections=num_detections,
                            num_classifications=num_classifications,
                        )
                        save_results_task_record.source_images.set(ml_task_record.source_images.all())
                        save_results_task_record.save()
                        job.logger.info(f"Submitted a save_results task for {task_id}.")

                        save_results_subtask = Subtask(task_id=task_result.id, task_name="save_results").dict()
                        subtasks_inprogress.append(save_results_subtask)
                        subtasks.append(save_results_subtask)

                    # Update the process_pipeline_request MLTaskRecord
                    ml_task_record.raw_results = json.loads(json.dumps(results.dict(), cls=DjangoJSONEncoder))
                    ml_task_record.raw_traceback = task.traceback
                    ml_task_record.num_captures = num_captures
                    ml_task_record.num_detections = num_detections
                    ml_task_record.num_classifications = num_classifications
                    ml_task_record.success = True if task.successful() else False
                    ml_task_record.save(
                        update_fields=[
                            "raw_results",
                            "raw_traceback",
                            "num_captures",
                            "num_detections",
                            "num_classifications",
                            "success",
                        ],
                    )
                    job.logger.info(
                        f"Updated MLTaskRecord for job {job.pk} with task ID {task_id} and task name {task_name}"
                    )
                elif task_name == "save_results":
                    # Update the MLTaskRecord
                    # TODO: save_results must return a json serializable result
                    # ml_task_record.raw_results = json.loads(json.dumps(results.dict(), cls=DjangoJSONEncoder))
                    # ml_task_record.raw_traceback = task.traceback
                    ml_task_record.success = True if task.successful() else False
                    # ml_task_record.save(update_fields=["raw_results", "raw_traceback", "success"])
                    ml_task_record.save(update_fields=["success"])
                    job.logger.info(
                        f"Updated MLTaskRecord for job {job.pk} with task ID {task_id} and task name {task_name}"
                    )
                else:
                    raise Exception(f"Unexpected task_name: {task_name}")
            else:
                job.logger.info(f"Sub-task {task_id} is still running")
                subtasks_inprogress.append(inprogress_subtask)

        job.inprogress_subtasks = subtasks_inprogress
        job.subtasks = subtasks
        job.save(update_fields=["inprogress_subtasks", "subtasks"], update_progress=False)

        # Now that the inprogress subtasks are up to date, update the job progress
        cls.update_job_progress(job)

        if subtasks_inprogress:
            return False
        else:
            return True

    @classmethod
    def update_job_progress(cls, job: "Job"):
        """Using the MLTaskRecords and the job subtask_ids, update the job progress."""
        inprogress_subtask_ids = [
            Subtask(**inprogress_subtask).task_id for inprogress_subtask in job.inprogress_subtasks
        ] or []
        all_subtask_ids = [Subtask(**subtask).task_id for subtask in job.subtasks]
        completed_subtask_ids = list(set(all_subtask_ids) - set(inprogress_subtask_ids))

        # At any time, we should have all process_pipeline_request in queue
        # len(inprogress_process_pipeline) + len(completed_process_pipeline) = total process_pipeline_request tasks
        inprogress_process_pipeline = job.ml_task_records.filter(
            task_id__in=inprogress_subtask_ids, task_name__in=["process_pipeline_request"]
        )
        completed_process_pipeline = job.ml_task_records.filter(
            task_id__in=completed_subtask_ids, task_name__in=["process_pipeline_request"]
        )

        inprogress_process_captures = sum([ml_task.num_captures for ml_task in inprogress_process_pipeline], 0)
        completed_process_captures = sum([ml_task.num_captures for ml_task in completed_process_pipeline], 0)
        failed_process_captures = sum(
            [ml_task.num_captures for ml_task in completed_process_pipeline if not ml_task.success], 0
        )

        # More save_results tasks will be queued as len(inprogress_process_pipeline) --> 0
        inprogress_save_results = job.ml_task_records.filter(
            task_id__in=inprogress_subtask_ids, task_name__in=["save_results"]
        )
        completed_save_results = job.ml_task_records.filter(
            task_id__in=completed_subtask_ids, task_name__in=["save_results"]
        )

        failed_process_tasks = (
            True if any([not task_record.success for task_record in completed_process_pipeline]) else False
        )
        failed_save_tasks = True if any([not task_record.success for task_record in completed_save_results]) else False
        any_failed_tasks = failed_process_tasks or failed_save_tasks

        total_results_captures = sum([ml_task.num_captures for ml_task in completed_save_results], 0)
        total_results_detections = sum([ml_task.num_detections for ml_task in completed_save_results], 0)
        total_results_classifications = sum([ml_task.num_classifications for ml_task in completed_save_results], 0)

        if inprogress_process_pipeline.count() > 0:
            job.progress.update_stage(
                "process",
                status=JobState.STARTED,
                progress=completed_process_pipeline.count()
                / (completed_process_pipeline.count() + inprogress_process_pipeline.count()),
                processed=completed_process_captures,
                remaining=inprogress_process_captures,
                failed=failed_process_captures,
            )
        else:
            job.progress.update_stage(  # @TODO: should we have a failure threshold of 50%?
                "process",
                status=JobState.FAILURE if failed_process_captures else JobState.SUCCESS,
                progress=1,
                processed=completed_process_captures,
                remaining=inprogress_process_captures,
                failed=failed_process_captures,
            )

        # Save results tasks may not have been submitted, or they may be in progress
        if inprogress_save_results.count() > 0 or inprogress_process_pipeline.count() > 0:
            job.progress.update_stage(
                "results",
                status=JobState.STARTED,
                # progress denominator is based on the total number of process_pipeline_request tasks
                # 1:1 ratio between save_results and process_pipeline_request tasks
                progress=completed_save_results.count()
                / (completed_process_pipeline.count() + inprogress_process_pipeline.count()),
                captures=total_results_captures,
                detections=total_results_detections,
                classifications=total_results_classifications,
            )
        else:
            job.progress.update_stage(
                "results",
                status=JobState.FAILURE if failed_save_tasks else JobState.SUCCESS,
                progress=1,
                captures=total_results_captures,
                detections=total_results_detections,
                classifications=total_results_classifications,
            )
            job.update_status(JobState.FAILURE if any_failed_tasks else JobState.SUCCESS, save=False)
            job.finished_at = datetime.datetime.now()

        # @TODO: look for places that job.save() is used and replace with update_fields
        # to minimize database writes this might cause job overwrites be careful
        job.save()

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

        if not job.pipeline:
            raise ValueError("No pipeline specified to process images in ML job")

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

        # End image collection stage
        job.save()

        job.logger.info(f"Processing {image_count} images with pipeline {job.pipeline.slug}")
        request_sent = time.time()
        try:
            tasks_to_watch = job.pipeline.process_images(
                images=images,
                job_id=job.pk,
                project_id=job.project.pk,
            )
            job.logger.info(
                "Submitted batch image processing tasks "
                "(task_name=process_pipeline_request) in "
                f"{time.time() - request_sent:.2f}s"
            )

        except Exception as e:
            job.logger.error(
                f"Failed to submit batch image processing tasks (task_name=process_pipeline_request): {e}"
            )
            # @TODO: this assumes ALL tasks failed; should allow as much as possible to complete
            # mark the job as failed
            job.progress.update_stage(
                "process",
                status=JobState.FAILURE,
                progress=1,
                failed=image_count,
                processed=0,
                remaining=image_count,
            )
            job.update_status(JobState.FAILURE)
            job.save()
        else:
            new_subtasks = [
                Subtask(task_id=task_to_watch, task_name="process_pipeline_request").dict()
                for task_to_watch in tasks_to_watch
            ]
            job.subtasks = (job.subtasks or []) + new_subtasks  # type: ignore
            job.inprogress_subtasks = (job.subtasks or []).copy()
            job.save()

            if job.inprogress_subtasks:
                # Schedule periodic celery task to update the subtask_ids and inprogress_subtasks
                cls.schedule_check_ml_job_status(job.pk)
            else:
                # No tasks were scheduled, mark the job as done
                job.progress.update_stage(
                    "process",
                    status=JobState.SUCCESS,
                    progress=1,
                )
                job.update_status(JobState.SUCCESS)


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
        job.progress.add_stage_param(cls.key, "Total files", "")
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


class UnknownJobType(JobType):
    name = "Unknown"
    key = "unknown"

    @classmethod
    def run(cls, job: "Job"):
        raise ValueError(f"Unknown job type '{job.job_type()}'")


VALID_JOB_TYPES = [MLJob, SourceImageCollectionPopulateJob, DataStorageSyncJob, UnknownJobType, DataExportJob]


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


class Subtask(pydantic.BaseModel):
    task_id: str
    task_name: str


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
    logs: JobLogs = SchemaField(JobLogs, default=JobLogs())
    params = models.JSONField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    subtasks = models.JSONField(default=list)  # list[Subtask] TODO add some validation?
    inprogress_subtasks = models.JSONField(default=list)  # list[Subtask] TODO add some validation?
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

    # For type hints
    ml_task_records: models.QuerySet["MLTaskRecord"]

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
            self.progress.add_stage_param(pipeline_stage.key, "Failed", "")

            saving_stage = self.progress.add_stage("Results")
            self.progress.add_stage_param(saving_stage.key, "Captures", "")
            self.progress.add_stage_param(saving_stage.key, "Detections", "")
            self.progress.add_stage_param(saving_stage.key, "Classifications", "")

        if save:
            self.save()

    def check_inprogress_subtasks(self) -> bool | None:
        """
        Check the status of the sub-tasks and update the job progress accordingly.

        Returns True if all subtasks are completed, False if any are still in progress.
        """
        job_type = self.job_type()
        return job_type.check_inprogress_subtasks(job=self)

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

    @classmethod
    def default_progress(cls) -> JobProgress:
        """Return the progress of each stage of this job as a dictionary"""
        return default_job_progress()

    @property
    def logger(self) -> logging.Logger:
        logger = logging.getLogger(f"ami.jobs.{self.pk}")
        # Also log output to a field on thie model instance
        logger.addHandler(JobLogHandler(self))
        logger.propagate = False
        return logger

    class Meta:
        ordering = ["-created_at"]
        # permissions = [
        #     ("run_job", "Can run a job"),
        #     ("cancel_job", "Can cancel a job"),


class MLTaskRecord(BaseModel):
    """
    A model to track the history of MLJob subtasks.
    Allows us to track the history of source images in a job.
    """

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="ml_task_records")
    task_id = models.CharField(max_length=255)
    source_images = models.ManyToManyField(SourceImage, related_name="ml_task_records")
    task_name = models.CharField(
        max_length=255,
        choices=[("process_pipeline_request", "process_pipeline_request"), ("save_results", "save_results")],
    )
    success = models.BooleanField(default=False)

    raw_results = models.JSONField(null=True, blank=True, default=dict)
    raw_traceback = models.TextField(null=True, blank=True)

    # recreate a process_pipeline_request task
    pipeline_request = SchemaField(PipelineRequest, null=True, blank=True)
    # recreate a save_results task
    pipeline_response = SchemaField(PipelineResultsResponse, null=True, blank=True)

    # track the progress of the job
    num_captures = models.IntegerField(default=0, help_text="Same as number of source_images")
    num_detections = models.IntegerField(default=0)
    num_classifications = models.IntegerField(default=0)

    def __str__(self):
        return f"MLTaskRecord(job={self.job.pk}, task_id={self.task_id}, task_name={self.task_name})"
