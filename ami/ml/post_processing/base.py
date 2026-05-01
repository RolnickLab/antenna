import abc
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
            self.job.progress.update_stage(self.job.job_type_key, progress=progress)
            self.job.save(update_fields=["progress"])

        else:
            # No job object — fallback to plain logging
            self.logger.info(f"[{self.name}] Progress {progress:.0%}")

    @abc.abstractmethod
    def run(self) -> None:
        """
        Run the task logic.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("BasePostProcessingTask subclasses must implement run()")
