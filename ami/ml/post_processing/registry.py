# Registry of available post-processing tasks
from ami.ml.post_processing.class_masking import ClassMaskingTask
from ami.ml.post_processing.rank_rollup import RankRollupTask
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask

POSTPROCESSING_TASKS = {
    SmallSizeFilterTask.key: SmallSizeFilterTask,
    ClassMaskingTask.key: ClassMaskingTask,
    RankRollupTask.key: RankRollupTask,
}


def get_postprocessing_task(key: str):
    """Return a post-processing task class by key."""
    return POSTPROCESSING_TASKS.get(key)
