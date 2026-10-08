"""A job's config as labelled rows, with the records it names resolved, for showing it to people.

A post-processing job stores its config in ``params["config"]``, validated by its task's
``config_schema``. The schema gives each field its title, its order and, through ``model_reference()``,
the type of record an id names.
"""

import dataclasses
import typing

from rest_framework import serializers

from ami.base.model_references import ModelRef, field_references, field_titles, is_record_id, resolve_model_references
from ami.base.serializers import ModelRefSerializer
from ami.jobs.models import Job
from ami.ml.post_processing.registry import get_postprocessing_task


@dataclasses.dataclass
class JobConfigField:
    """One field of a job's config: its title from the task's config schema, and the record it names, if any."""

    key: str
    label: str
    value: typing.Any
    ref: ModelRef | None = None


class JobConfigFieldSerializer(serializers.Serializer):
    """One field of a job's config. ``label`` is the title the task's config schema gives it, else the key."""

    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.JSONField(allow_null=True)
    ref = ModelRefSerializer(allow_null=True, help_text="The record the field names, when it names one.")


def job_config(job: Job | None) -> dict | None:
    """The config a post-processing job ran with, or None for any other job or malformed params."""
    params = job.params if job is not None else None
    config = params.get("config") if isinstance(params, dict) else None
    return config if isinstance(config, dict) else None


def job_config_fields(jobs: typing.Iterable[Job]) -> dict[int, list[JobConfigField]]:
    """Each job's config fields by job id, resolving every record id they name with one query per type."""
    specs = {job.pk: _field_specs(job) for job in jobs}
    wanted = [(ref_type, value) for fields in specs.values() for _, _, value, ref_type in fields if ref_type]
    resolved = resolve_model_references(wanted) if wanted else {}
    return {
        job_id: [
            JobConfigField(key, label, value, resolved[(ref_type, value)] if ref_type else None)
            for key, label, value, ref_type in fields
        ]
        for job_id, fields in specs.items()
    }


def _field_specs(job: Job) -> list[tuple[str, str, typing.Any, str | None]]:
    """``(key, label, value, reference type)`` per field, labelled, typed and ordered by the task's config schema.

    The stored config's key order is not kept (Postgres orders a JSON object's keys), so fields follow the
    schema and any key it does not declare comes after. A job whose task is not registered shows its
    config by key, naming no records.
    """
    config = job_config(job) or {}
    task_key = job.params.get("task") if config else None
    task = get_postprocessing_task(task_key) if isinstance(task_key, str) else None
    titles = field_titles(task.config_schema) if task else {}
    references = field_references(task.config_schema) if task else {}
    keys = [key for key in titles if key in config] + [key for key in config if key not in titles]
    return [
        (key, titles.get(key) or key, config[key], references.get(key) if is_record_id(config[key]) else None)
        for key in keys
    ]
