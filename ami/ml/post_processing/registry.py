# Registry of available post-processing tasks
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask
from ami.ml.post_processing.tracking_task import TrackingTask

POSTPROCESSING_TASKS = {
    SmallSizeFilterTask.key: SmallSizeFilterTask,
    TrackingTask.key: TrackingTask,
}


def get_postprocessing_task(key: str):
    """Return a post-processing task class by key."""
    return POSTPROCESSING_TASKS.get(key)
