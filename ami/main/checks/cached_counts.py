"""Reconcile drift on ``CachedCountField`` columns.

Cached count columns (e.g. ``Deployment.captures_count``,
``SourceImageCollection.source_images_count``) are kept current via signals
and explicit ``update_calculated_fields`` calls. Bulk write paths that skip
signals — ``bulk_create``, ``bulk_update``, raw SQL, some ML post-processors
— silently drift the stored value out of sync with the underlying rows.

This check discovers every model that declares one or more
``CachedCountField`` columns, finds rows whose stored values disagree with
a fresh recompute via ``instance.update_calculated_fields(save=False)``,
and either reports or repairs them.

Run via ``manage.py check_data_integrity`` (when PR #1188 lands) or via
the ``reconcile_cached_counts`` Celery task.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from django.apps import apps

from ami.base.models import BaseModel, CachedCountField
from ami.main.checks.schemas import IntegrityCheckResult

logger = logging.getLogger(__name__)


def _cached_count_field_names(model: type[BaseModel]) -> list[str]:
    fields = model._meta.get_fields()  # type: ignore[attr-defined]
    return [f.name for f in fields if isinstance(f, CachedCountField) and f.name]


def discover_cached_count_fields() -> dict[type[BaseModel], list[str]]:
    """Return models that declare one or more ``CachedCountField`` columns."""
    result: dict[type[BaseModel], list[str]] = {}
    for model in apps.get_models():
        if not issubclass(model, BaseModel):
            continue
        cached = _cached_count_field_names(model)
        if cached:
            result[model] = cached
    return result


def _scope_to_project(qs, model: type[BaseModel], project_id: int | None):
    if project_id is None:
        return qs
    project_accessor = model.get_project_accessor()
    if project_accessor and project_accessor != "projects":
        return qs.filter(**{f"{project_accessor}_id": project_id})
    return qs


def find_stale_cached_counts(
    model: type[BaseModel],
    project_id: int | None = None,
) -> Iterator[tuple[BaseModel, dict[str, int | None], dict[str, int | None]]]:
    """Yield ``(instance, stored, computed)`` for rows whose cached counts drift.

    Iterates the queryset row-by-row and calls ``update_calculated_fields(save=False)``
    on a fresh copy so the stored row stays untouched. Heavy on large tables;
    callers should scope by ``project_id`` whenever the check is interactive.
    """
    cached_fields = _cached_count_field_names(model)
    if not cached_fields:
        return
    qs = _scope_to_project(model.objects.all(), model, project_id)
    for instance in qs.iterator():
        stored = {f: getattr(instance, f) for f in cached_fields}
        instance.update_calculated_fields(save=False)
        computed = {f: getattr(instance, f) for f in cached_fields}
        if stored != computed:
            yield instance, stored, computed


def reconcile_cached_counts(
    model: type[BaseModel] | None = None,
    project_id: int | None = None,
    dry_run: bool = True,
) -> IntegrityCheckResult:
    """Repair stale cached counts. Pass ``model=None`` to sweep all models."""
    models_to_check = [model] if model else list(discover_cached_count_fields().keys())
    result = IntegrityCheckResult()
    for m in models_to_check:
        for instance, stored, computed in find_stale_cached_counts(m, project_id=project_id):
            result.checked += 1
            logger.info(
                "Stale cached counts on %s pk=%s: stored=%s computed=%s",
                m.__name__,
                instance.pk,
                stored,
                computed,
            )
            if dry_run:
                continue
            try:
                instance.update_cached_counts(run_async=False)
                result.fixed += 1
            except Exception:
                logger.exception("Failed to reconcile %s pk=%s", m.__name__, instance.pk)
                result.unfixable += 1
    return result
