import abc
import inspect
import logging
import typing
from typing import Any, Optional

import pydantic

from ami.ml.models import Algorithm
from ami.ml.models.algorithm import AlgorithmTaskType

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job


class BasePostProcessingTask(abc.ABC):
    """
    Abstract base class for all post-processing tasks.

    Subclasses must declare a Pydantic ``config_schema`` describing the shape of
    ``Job.params['config']``. Config is validated at task construction so bad
    payloads fail fast in worker logs (and earlier still — admin triggers and
    other callers should validate via the same schema before enqueueing a Job).
    """

    # Each task must override these
    key: str
    name: str
    config_schema: type[pydantic.BaseModel]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only enforce the contract on concrete tasks. An abstract intermediary
        # (e.g. a shared mixin with an unimplemented abstractmethod) may legitimately
        # defer key/name/config_schema to its concrete subclasses.
        if inspect.isabstract(cls):
            return
        required_attrs = ["key", "name", "config_schema"]
        for attr in required_attrs:
            if not hasattr(cls, attr) or getattr(cls, attr) is None:
                raise TypeError(f"{cls.__name__} must define '{attr}' class attribute")

    def __init__(
        self,
        job: Optional["Job"] = None,
        logger: logging.Logger | None = None,
        **config: Any,
    ):
        self.job = job
        self.config: pydantic.BaseModel = self.config_schema(**config)
        # Choose the right logger
        if logger is not None:
            self.logger = logger
        elif job is not None:
            self.logger = job.logger
        else:
            self.logger = logging.getLogger(f"ami.post_processing.{self.key}")

        algorithm, _ = Algorithm.objects.get_or_create(
            name=self.name,
            key=self.key,
            defaults={
                "description": f"Post-processing task: {self.key}",
                "task_type": AlgorithmTaskType.POST_PROCESSING.value,
            },
        )
        self.algorithm: Algorithm = algorithm

        self.logger.info(f"Initialized {self.name} with config={self.config.dict()}, job={job}")

    def update_progress(self, progress: float):
        """
        Update progress if job is present, otherwise just log.
        """

        if self.job:
            # Imported here because ami.jobs.models imports the post-processing
            # registry, so a module-level import would be circular.
            from ami.jobs.models import JobState

            # Job.update_progress only promotes a stage out of CREATED once its
            # progress exceeds zero, so a stage reporting exactly 0% stays labelled
            # "Waiting to start". Promote it here, and only from CREATED, so a
            # heartbeat can never pull a finished or cancelled stage backwards.
            # See #1376.
            stage = self.job.progress.get_stage(self.job.job_type_key)
            status = {"status": JobState.STARTED} if stage.status == JobState.CREATED else {}
            self.job.progress.update_stage(self.job.job_type_key, progress=progress, **status)
            # Bump updated_at alongside progress: the stale-job reaper
            # (check_stale_jobs) revokes running jobs whose updated_at is older
            # than STALLED_JOBS_MAX_MINUTES. A long post-processing run that only
            # touched "progress" would look frozen and be reaped mid-flight.
            self.job.save(update_fields=["progress", "updated_at"])

        else:
            # No job object — fallback to plain logging
            self.logger.info(f"[{self.name}] Progress {progress:.0%}")

    def report_stage_metrics(self, metrics: dict[str, Any]):
        """Surface human-readable counters on the job's post-processing stage.

        Each ``{label: value}`` pair becomes a stage parameter visible on the Jobs
        admin page (e.g. ``{"Detections checked": 540, "Flagged": 12}``), so an
        operator can see what a run examined and changed without reading the log.
        Labels may contain spaces; pass them as dict keys rather than kwargs.

        Falls back to a single log line when running jobless (tests, management
        commands), so the same call site works in both contexts.
        """
        if not self.job:
            self.logger.info(f"[{self.name}] " + ", ".join(f"{k}: {v}" for k, v in metrics.items()))
            return

        stage_key = self.job.job_type_key
        for label, value in metrics.items():
            self.job.progress.add_or_update_stage_param(stage_key, label, value)
        # Bump updated_at so the stale-job reaper sees an actively-progressing
        # run; see update_progress for the full reasoning.
        self.job.save(update_fields=["progress", "updated_at"])

    @abc.abstractmethod
    def run(self) -> None:
        """
        Run the task logic.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("BasePostProcessingTask subclasses must implement run()")
