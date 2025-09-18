import logging
from typing import Any

logger = logging.getLogger(__name__)

POST_PROCESSING_REGISTRY = {}


def register_step(cls):
    """Decorator to register a post-processing step."""
    POST_PROCESSING_REGISTRY[cls.name] = cls()
    return cls


class PostProcessingStep:
    """Base interface for a post-processing step."""

    name: str = "base_step"
    description: str = "Base step (does nothing)"
    default_enabled: bool = False

    def apply(self, pipeline_input: Any, pipeline_output: Any) -> tuple[Any, Any]:
        """Process and return modified input/output."""
        raise NotImplementedError
