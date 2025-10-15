import abc
import logging
from typing import Any

from ami.jobs.models import Job
from ami.ml.models import Algorithm
from ami.ml.models.algorithm import AlgorithmTaskType

# Registry of available post-processing tasks
POSTPROCESSING_TASKS: dict[str, type["BasePostProcessingTask"]] = {}


def register_postprocessing_task(task_cls: type["BasePostProcessingTask"]):
    """
    Decorator to register a post-processing task in the global registry.
    Each task must define a unique `key`.
    Ensures an Algorithm entry exists for this task.
    """
    if not hasattr(task_cls, "key") or not task_cls.key:
        raise ValueError(f"Task {task_cls.__name__} missing required 'key' attribute")

    # Register the task
    POSTPROCESSING_TASKS[task_cls.key] = task_cls
    return task_cls


def get_postprocessing_task(name: str) -> type["BasePostProcessingTask"] | None:
    """
    Get a task class by its registry key.
    Returns None if not found.
    """
    return POSTPROCESSING_TASKS.get(name)


class BasePostProcessingTask(abc.ABC):
    """
    Abstract base class for all post-processing tasks.
    """

    # Each task must override these
    key: str = ""
    name: str = ""

    def __init__(
        self,
        job: Job | None = None,
        logger: logging.Logger | None = None,
        **config: Any,
    ):
        self.job = job
        self.config = config
        # Choose the right logger
        if logger is not None:
            self.logger = logger
        elif job is not None:
            self.logger = job.logger
        else:
            self.logger = logging.getLogger(f"ami.post_processing.{self.key}")

        algorithm, _ = Algorithm.objects.get_or_create(
            name=self.__class__.__name__,
            defaults={
                "description": f"Post-processing task: {self.key}",
                "task_type": AlgorithmTaskType.POST_PROCESSING.value,
            },
        )
        self.algorithm: Algorithm = algorithm

        self.logger.info(f"Initialized {self.__class__.__name__} with config={self.config}, job={job}")

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
