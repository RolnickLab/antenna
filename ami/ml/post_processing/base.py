# ami/ml/post_processing/base.py

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

    # Ensure Algorithm object exists for this task
    algorithm, _ = Algorithm.objects.get_or_create(
        name=task_cls.__name__,
        defaults={
            "description": f"Post-processing task: {task_cls.key}",
            "task_type": AlgorithmTaskType.POST_PROCESSING.value,
        },
    )

    # Attach the Algorithm object to the task class
    task_cls.algorithm = algorithm

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

    def __init__(self, **config: Any):
        """
        Initialize task with configuration parameters.
        """
        self.config: dict[str, Any] = config
        self.logger = logging.getLogger(f"ami.post_processing.{self.key}")

    @abc.abstractmethod
    def run(self, job: Job) -> None:
        """
        Run the task logic.
        Must be implemented by subclasses.
        The job parameter provides context (project, logs, etc.).
        """
        raise NotImplementedError("Subclasses must implement run()")

    def log_config(self, job: Job):
        """
        Helper to log the task configuration at start.
        """
        job.logger.info(f"Running task {self.name} ({self.key}) with config: {self.config}")
