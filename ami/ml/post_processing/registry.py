# Registry of available post-processing tasks
from ami.ml.post_processing.class_masking import ClassMaskingTask
from ami.ml.post_processing.feature_vectors import AddFeatureVectorsTask
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask

POSTPROCESSING_TASKS = {
    SmallSizeFilterTask.key: SmallSizeFilterTask,
    ClassMaskingTask.key: ClassMaskingTask,
    AddFeatureVectorsTask.key: AddFeatureVectorsTask,
}


def get_postprocessing_task(key: str):
    """Return a post-processing task class by key."""
    return POSTPROCESSING_TASKS.get(key)
