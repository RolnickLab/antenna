"""Job builder for the Events entry point to Occurrence Tracking.

Tracking runs per session, and the Events changelist lets an operator pick
sessions from several projects at once. A Job belongs to exactly one project, so
the selection is partitioned by project: one Job per project, carrying that
project's event ids.
"""
from __future__ import annotations

import collections
from typing import Any

import pydantic
from django.db import transaction

from ami.jobs.models import Job
from ami.ml.post_processing.admin.actions import ConfigValidationErrors
from ami.ml.post_processing.base import BasePostProcessingTask


def build_tracking_jobs_for_events(
    *,
    config: dict[str, Any],
    queryset,
    task_cls: type[BasePostProcessingTask],
    form_field_names: set[str],
    **_unused: Any,
) -> list[int]:
    """Enqueue one tracking Job per project across the selected events."""
    events_by_project: dict[Any, list[int]] = collections.defaultdict(list)
    orphans: list[int] = []
    for event in queryset:
        if event.project_id is None:
            orphans.append(event.pk)
        else:
            events_by_project[event.project_id].append(event.pk)

    errors: list[tuple[str | None, str]] = []
    if orphans:
        errors.append((None, f"Session(s) {sorted(orphans)} have no project. Set their project first."))

    validated: list[tuple[int, pydantic.BaseModel]] = []
    for project_id, event_ids in events_by_project.items():
        try:
            validated.append((project_id, task_cls.config_schema(**{**config, "event_ids": sorted(event_ids)})))
        except pydantic.ValidationError as exc:
            errors.extend((None, err.get("msg", "Invalid value")) for err in exc.errors())

    if errors:
        raise ConfigValidationErrors(errors)

    job_pks: list[int] = []
    with transaction.atomic():
        for project_id, model in validated:
            job = Job.objects.create(
                name=f"Post-processing: {task_cls.name} on {len(model.event_ids)} session(s)",
                project_id=project_id,
                job_type_key="post_processing",
                params={"task": task_cls.key, "config": model.dict()},
            )
            job.enqueue()
            job_pks.append(job.pk)
    return job_pks
