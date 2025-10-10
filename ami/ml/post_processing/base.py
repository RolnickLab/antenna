# ami/ml/post_processing/base.py

import abc
import logging
from typing import Any, Optional

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

    key: str = ""
    name: str = ""

    def __init__(
        self,
        job: Optional["Job"] = None,
        task_logger: logging.Logger | None = None,
        **config: Any,
    ):
        """
        Initialize task with optional job and logger context.
        """
        self.job = job
        self.config: dict[str, Any] = config

        if job:
            self.logger = job.logger
        elif task_logger:
            self.logger = task_logger
        else:
            self.logger = logging.getLogger(f"ami.post_processing.{self.key}")
        self.log_config()

    @abc.abstractmethod
    def run(self) -> None:
        """Run the task logic. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement run()")

    def log_config(self):
        """Helper to log the task configuration at start."""
        self.logger.info(f"Running task {self.name} ({self.key}) with config: {self.config}")
