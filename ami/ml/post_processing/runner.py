import logging
from typing import Any

from .base import POST_PROCESSING_REGISTRY

logger = logging.getLogger(__name__)


def run_postprocessing(
    pipeline_input: Any,
    pipeline_output: Any,
    enabled_steps: list[str] | None = None,
) -> tuple[Any, Any]:
    """
    Run all enabled post-processing steps on pipeline results.
    """
    steps = enabled_steps or [name for name, step in POST_PROCESSING_REGISTRY.items() if step.default_enabled]

    logger.info(f"Running post-processing steps: {steps}")

    for name in steps:
        step = POST_PROCESSING_REGISTRY.get(name)
        if not step:
            logger.warning(f"Post-processing step '{name}' not found, skipping")
            continue
        pipeline_input, pipeline_output = step.apply(pipeline_input, pipeline_output)

    return pipeline_input, pipeline_output
