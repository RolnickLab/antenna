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


# Post-processing tasks a project member may start through the jobs API, with the config
# fields a member may set. Every other field must keep its schema default. Tasks not listed
# here are staff tools: superusers can still start them from the Create Job dialog.
MEMBER_POST_PROCESSING_TASKS: dict[str, frozenset[str]] = {}


def staff_only_config_fields(task_key: str, config: dict) -> list[str]:
    """Return the fields in ``config`` that only staff may set away from their default."""
    schema_fields = POSTPROCESSING_TASKS[task_key].config_schema.__fields__
    allowed = MEMBER_POST_PROCESSING_TASKS.get(task_key, frozenset())
    return sorted(
        name
        for name, value in config.items()
        if name in schema_fields and name not in allowed and value != schema_fields[name].default
    )
