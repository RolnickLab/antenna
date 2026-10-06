# Registry of available post-processing tasks
from ami.ml.post_processing.class_masking import ClassMaskingTask
from ami.ml.post_processing.small_size_filter import SmallSizeFilterTask

POSTPROCESSING_TASKS = {
    SmallSizeFilterTask.key: SmallSizeFilterTask,
    ClassMaskingTask.key: ClassMaskingTask,
}


def get_postprocessing_task(key: str):
    """Return a post-processing task class by key."""
    return POSTPROCESSING_TASKS.get(key)


def config_setting_labels(key: str | None) -> dict[str, str]:
    """The title each setting declares in the task's config schema, for settings that declare one."""
    task_cls = POSTPROCESSING_TASKS.get(key) if isinstance(key, str) else None
    if task_cls is None:
        return {}
    fields = task_cls.config_schema.__fields__
    return {name: field.field_info.title for name, field in fields.items() if field.field_info.title}
