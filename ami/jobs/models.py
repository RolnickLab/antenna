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
from guardian.shortcuts import get_perms

from ami.base.models import BaseModel
from ami.base.schemas import ConfigurableStage, ConfigurableStageParam
from ami.jobs.tasks import run_job
from ami.main.models import Deployment, Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.post_processing.registry import get_postprocessing_task
from ami.ml.schemas import PipelineRequest, PipelineResultsResponse
from ami.ml.signals import get_worker_name, subscribe_celeryworker_to_pipeline_queues
from ami.ml.tasks import check_ml_job_status
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

    @classmethod
    def check_inprogress_subtasks(cls, job: "Job") -> bool:
        """
        Check the status of the MLJob subtasks and update/create MLTaskRecords
        based on if the subtasks fail/succeed.
        This is the main function that keeps track of the MLJob's state and all of its subtasks.

        Returns True if all subtasks are completed.
        """
        assert job.pipeline is not None, "Job pipeline is not set"

        inprogress_subtasks = (
            job.ml_task_records.exclude(
                status__in=[
                    MLSubtaskState.FAIL.name,
                    MLSubtaskState.SUCCESS.name,
                ]
            )
            .filter(
                created_at__gte=job.started_at,
            )
            .all()
        )
        if len(inprogress_subtasks) == 0:
            # No tasks inprogress, update the job progress
            job.logger.info("No inprogress subtasks left.")
            cls.update_job_progress(job)
            return True

        save_results_task_record = {  # if pipeline responses are produced, this task will be saved to the db
            "job": job,
            "task_id": None,
            "status": MLSubtaskState.PENDING.name,  # save result tasks are not started immediately
            "task_name": MLSubtaskNames.save_results.name,
            "num_captures": 0,
            "num_detections": 0,
            "num_classifications": 0,
        }
        save_results_to_save = []  # list of tuples (pipeline response, source images)
        inprogress_subtasks_to_update = []
        for inprogress_subtask in inprogress_subtasks:
            task_name = inprogress_subtask.task_name
            task_id = inprogress_subtask.task_id
            if not task_id:
                assert (
                    task_name == MLSubtaskNames.save_results.name
                ), "Only save results tasks can have no task_id and be in a PENDING state."
                # Ensure no other STARTED save_results tasks
                if (
                    job.ml_task_records.filter(
                        status=MLSubtaskState.STARTED.name,
                        task_name=MLSubtaskNames.save_results.name,
                        created_at__gte=job.started_at,
                    ).count()
                    == 0
                ):
                    assert (
                        inprogress_subtask.pipeline_response is not None
                    ), "Save results task must have a pipeline response"
                    # Start the save results task now
                    save_results_task = job.pipeline.save_results_async(
                        results=inprogress_subtask.pipeline_response, job_id=job.pk
                    )
                    inprogress_subtask.status = MLSubtaskState.STARTED.name
                    inprogress_subtask.task_id = save_results_task.id
                    task_id = save_results_task.id
                    inprogress_subtask.save()
                    job.logger.info(f"Started save results task {inprogress_subtask.task_id}")
                else:
                    job.logger.info("A save results task is already in progress, will not start another one yet.")
                    continue

            task = AsyncResult(task_id)
            if task.ready():
                inprogress_subtasks_to_update.append(inprogress_subtask)
                inprogress_subtask.status = (
                    MLSubtaskState.SUCCESS.name if task.successful() else MLSubtaskState.FAIL.name
                )
                inprogress_subtask.raw_traceback = task.traceback

                if task.traceback:
                    # TODO: Error logs will have many tracebacks
                    # could add some processing to provide a concise error summary
                    job.logger.error(f"Subtask {task_name} ({task_id}) failed: {task.traceback}")

                results_dict = task.result
                if task_name == MLSubtaskNames.process_pipeline_request.name:
                    results = PipelineResultsResponse(**results_dict)
                    num_captures = len(results.source_images)
                    num_detections = len(results.detections)
                    num_classifications = len([c for d in results.detections for c in d.classifications])
                    # Update the process_pipeline_request MLTaskRecord
                    inprogress_subtask.raw_results = json.loads(json.dumps(results.dict(), cls=DjangoJSONEncoder))
                    inprogress_subtask.num_captures = num_captures
                    inprogress_subtask.num_detections = num_detections
                    inprogress_subtask.num_classifications = num_classifications

                    if results.source_images or results.detections:
                        save_results_to_save.append((results, inprogress_subtask.source_images.all()))
                        save_results_task_record["num_captures"] += num_captures
                        save_results_task_record["num_detections"] += num_detections
                        save_results_task_record["num_classifications"] += num_classifications
                elif task_name == MLSubtaskNames.save_results.name:
                    pass
                else:
                    raise Exception(f"Unexpected task_name: {task_name}")

                # To avoid long running jobs from taking a long time to update, bulk update every 10 tasks
                # Bulk save the updated inprogress subtasks
                if len(inprogress_subtasks_to_update) >= 10:
                    MLTaskRecord.objects.bulk_update(
                        inprogress_subtasks_to_update,
                        [
                            "status",
                            "raw_traceback",
                            "raw_results",
                            "num_captures",
                            "num_detections",
                            "num_classifications",
                        ],
                    )

                    cls.update_job_progress(job)

                    # Reset the lists
                    inprogress_subtasks_to_update = []

        assert job.pipeline is not None, "Job pipeline is not set"
        # submit a single save results task
        if len(save_results_to_save) > 0:
            created_task_record = MLTaskRecord.objects.create(**save_results_task_record)
            for _, source_images in save_results_to_save:
                created_task_record.source_images.add(*source_images)
            pipeline_results = [t[0] for t in save_results_to_save]
            combined_pipeline_results = (
                pipeline_results[0].combine_with(pipeline_results[1:])
                if len(pipeline_results) > 1
                else pipeline_results[0]
            )
            created_task_record.pipeline_response = combined_pipeline_results
            created_task_record.save()

        # Bulk save the remaining items
        # Bulk save the updated inprogress subtasks
        MLTaskRecord.objects.bulk_update(
            inprogress_subtasks_to_update,
            [
                "status",
                "raw_traceback",
                "raw_results",
                "num_captures",
                "num_detections",
                "num_classifications",
            ],
        )

        cls.update_job_progress(job)

        inprogress_subtasks = (
            job.ml_task_records.exclude(
                status__in=[
                    MLSubtaskState.FAIL.name,
                    MLSubtaskState.SUCCESS.name,
                ]
            )
            .filter(
                created_at__gte=job.started_at,
            )
            .all()
        )
        total_subtasks = job.ml_task_records.all().count()
        if inprogress_subtasks.count() > 0:
            job.logger.info(
                f"{inprogress_subtasks.count()} inprogress subtasks remaining out of {total_subtasks} total subtasks."
            )
            inprogress_task_ids = [task.task_id for task in inprogress_subtasks]
            job.logger.info(f"Subtask ids: {inprogress_task_ids}")  # TODO: remove this? not very useful to the user
            return False
        else:
            job.logger.info("No inprogress subtasks left.")
            return True

    @classmethod
    def update_job_progress(cls, job: "Job"):
        """
        Using the MLTaskRecords of a related Job, update the job progress.
        This function only updates the UI's job status. No new data is created here.
        """
        # At any time, we should have all process_pipeline_request in queue
        # That is: len(inprogress_process_pipeline) + len(completed_process_pipeline)
        # = total process_pipeline_request tasks
        inprogress_process_pipeline = job.ml_task_records.filter(
            status=MLSubtaskState.STARTED.name,
            task_name=MLSubtaskNames.process_pipeline_request.name,
            created_at__gte=job.started_at,
        )
        completed_process_pipelines = job.ml_task_records.filter(
            status__in=[MLSubtaskState.FAIL.name, MLSubtaskState.SUCCESS.name],
            task_name=MLSubtaskNames.process_pipeline_request.name,
            created_at__gte=job.started_at,
        )

        # Calculate process stage stats
        inprogress_process_captures = sum([ml_task.num_captures for ml_task in inprogress_process_pipeline], 0)
        completed_process_captures = sum([ml_task.num_captures for ml_task in completed_process_pipelines], 0)
        failed_process_captures = sum(
            [
                ml_task.num_captures
                for ml_task in completed_process_pipelines
                if ml_task.status != MLSubtaskState.SUCCESS.name
            ],
            0,
        )

        # Update the process stage
        if inprogress_process_pipeline.count() > 0:
            job.progress.update_stage(
                "process",
                status=JobState.STARTED,
                progress=completed_process_pipelines.count()
                / (completed_process_pipelines.count() + inprogress_process_pipeline.count()),
                processed=completed_process_captures,
                remaining=inprogress_process_captures,
                failed=failed_process_captures,
            )
        else:
            job.progress.update_stage(  # @TODO: should we have a failure threshold of 50%?
                "process",
                status=JobState.FAILURE if failed_process_captures > 0 else JobState.SUCCESS,
                progress=1,
                processed=completed_process_captures,
                remaining=inprogress_process_captures,
                failed=failed_process_captures,
            )

        inprogress_save_results = job.ml_task_records.filter(
            status__in=[
                MLSubtaskState.STARTED.name,
                MLSubtaskState.PENDING.name,
            ],
            task_name=MLSubtaskNames.save_results.name,
            created_at__gte=job.started_at,
        )
        completed_save_results = job.ml_task_records.filter(
            status__in=[MLSubtaskState.FAIL.name, MLSubtaskState.SUCCESS.name],
            task_name=MLSubtaskNames.save_results.name,
            created_at__gte=job.started_at,
        )
        succeeded_save_results = job.ml_task_records.filter(
            status=MLSubtaskState.SUCCESS.name,
            task_name=MLSubtaskNames.save_results.name,
            created_at__gte=job.started_at,
        )

        # Calculate results stage stats
        failed_process_tasks = (
            True
            if any([task_record.status != MLSubtaskState.SUCCESS.name for task_record in completed_process_pipelines])
            else False
        )
        num_failed_save_tasks = sum(
            [1 for ml_task in completed_save_results if ml_task.status != MLSubtaskState.SUCCESS.name],
            0,
        )
        failed_save_tasks = num_failed_save_tasks > 0
        any_failed_tasks = failed_process_tasks or failed_save_tasks

        # only include captures/detections/classifications which we successfully saved
        total_results_captures = sum([ml_task.num_captures for ml_task in succeeded_save_results], 0)
        total_results_detections = sum([ml_task.num_detections for ml_task in succeeded_save_results], 0)
        total_results_classifications = sum([ml_task.num_classifications for ml_task in succeeded_save_results], 0)

        # Update the results stage
        if inprogress_save_results.count() > 0 or inprogress_process_pipeline.count() > 0:
            job.progress.update_stage(
                "results",
                status=JobState.STARTED,
                # Save results tasks may not have been submitted, or they may be in progress
                # progress denominator is based on the total number of process_pipeline_request tasks
                # 1:1 ratio between save_results and process_pipeline_request tasks
                progress=completed_save_results.count()
                / (completed_process_pipelines.count() + inprogress_process_pipeline.count()),
                captures=total_results_captures,
                detections=total_results_detections,
                classifications=total_results_classifications,
                failed=num_failed_save_tasks,
            )
        else:
            job.progress.update_stage(
                "results",
                status=JobState.FAILURE if failed_save_tasks else JobState.SUCCESS,
                progress=1,
                captures=total_results_captures,
                detections=total_results_detections,
                classifications=total_results_classifications,
                failed=num_failed_save_tasks,
            )

            # The ML job is completed, log general job stats
            job.update_status(JobState.FAILURE if any_failed_tasks else JobState.SUCCESS, save=False)

            if any_failed_tasks:
                failed_save_task_ids = [
                    completed_save_result.task_id
                    for completed_save_result in completed_save_results
                    if completed_save_result.status == MLSubtaskState.FAIL.name
                ]
                job.logger.error(
                    f"Failed save result task ids = {failed_save_task_ids}"
                )  # TODO: more for dev debugging?

                failed_process_task_ids = [
                    completed_process_pipeline.task_id
                    for completed_process_pipeline in completed_process_pipelines
                    if completed_process_pipeline.status == MLSubtaskState.FAIL.name
                ]
                job.logger.error(
                    f"Failed process task ids = {failed_process_task_ids}"
                )  # TODO: more for dev debugging?

            job.finished_at = datetime.datetime.now()

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
            # Ensures queues we subscribe to are always up to date
            logger.info("Subscribe to all pipeline queues prior to processing...")
            worker_name = get_worker_name()
            subscribe_celeryworker_to_pipeline_queues(worker_name)

            job.pipeline.schedule_process_images(
                images=images,
                job_id=job.pk,
                project_id=job.project.pk,
            )
            job.logger.info(
                "Submitted batch image processing tasks "
                f"(task_name={MLSubtaskNames.process_pipeline_request.name}) in "
                f"{time.time() - request_sent:.2f}s"
            )

        except Exception as e:
            job.logger.error(f"Failed to submit all images: {e}")
            job.update_status(JobState.FAILURE)
            job.save()
        else:
            subtasks = job.ml_task_records.filter(created_at__gte=job.started_at)
            if subtasks.count() == 0:
                # No tasks were scheduled, mark the job as done
                job.logger.info("No subtasks were scheduled, ending the job.")
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
            else:
                job.logger.info(
                    f"Continue processing the remaining {subtasks.count()} process image request subtasks."
                )
                from django.db import transaction

                transaction.on_commit(lambda: check_ml_job_status.apply_async([job.pk]))
        finally:
            # TODO: clean up?
            pass


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


class MLSubtaskNames(str, OrderedEnum):
    process_pipeline_request = "process_pipeline_request"
    save_results = "save_results"


class MLSubtaskState(str, OrderedEnum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class MLTaskRecord(BaseModel):
    """
    A model to track the history of MLJob subtasks.
    Allows us to track the history of source images in a job.
    """

    job = models.ForeignKey("Job", on_delete=models.CASCADE, related_name="ml_task_records")
    task_id = models.CharField(max_length=255, null=True, blank=True)
    source_images = models.ManyToManyField(SourceImage, related_name="ml_task_records")
    task_name = models.CharField(
        max_length=255,
        default=MLSubtaskNames.process_pipeline_request.name,
        choices=MLSubtaskNames.choices(),
    )
    status = models.CharField(
        max_length=255,
        default=MLSubtaskState.STARTED.name,
        choices=MLSubtaskState.choices(),
    )

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

    def clean(self):
        if self.status == MLSubtaskState.PENDING.name and self.task_name != MLSubtaskNames.save_results.name:
            raise ValueError(f"{self.task_name} tasks cannot have a PENDING status.")


class Job(BaseModel):
    """A job to be run by the scheduler"""

    # Hide old failed jobs after 3 days
    FAILED_CUTOFF_HOURS = 24 * 3

    name = models.CharField(max_length=255)
    queue = models.CharField(max_length=255, default="default")
    last_checked = models.DateTimeField(null=True, blank=True)
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
        self.progress = self.progress or self.get_default_progress()

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
