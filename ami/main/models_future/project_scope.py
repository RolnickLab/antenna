"""The ``project`` column of algorithm-output tables, filled from the row's parent.

New tables carry ``project`` NOT NULL so permission checks and per-project queries need no
join. Until composite foreign keys enforce it (see #1453), every writer fills the column
through ``fill_project_ids`` and ``project_mismatch_counts`` reports rows that drifted.

A model opts in with ``project_parent_path``: the path from the row to the object whose
``project`` it copies, which must also have a ``deployment`` (a capture, occurrence or session).
A table whose rows point at one of several targets declares ``project_parent_paths`` instead,
one path per target; each row copies the project of the one target it has.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from django.db import models
from django.db.models.functions import Coalesce

logger = logging.getLogger(__name__)

# How many disagreeing parents a warning names.
IDS_TO_LOG = 10


class ProjectScopeError(ValueError):
    """A row's parent has no project, directly or through its deployment."""


def project_ids_for(model: type[models.Model], ids: Iterable[int], via: str = "", label: str = "") -> dict[int, int]:
    """The project each ``model`` row belongs to, in one query, keyed by its primary key.

    ``via`` is the path from ``model`` to the parent that holds the project (empty when
    ``model`` holds it). The parent's own project wins; when it is empty, its deployment's
    project is used; when both are empty, ``ProjectScopeError`` is raised. A parent whose
    project disagrees with its deployment's keeps its own, and the disagreement is logged.
    """
    prefix = f"{via}__" if via else ""
    ids = set(ids)
    rows = (
        model.objects.filter(pk__in=ids)
        .order_by()
        .values_list("pk", f"{prefix}project_id", f"{prefix}deployment__project_id")
    )
    resolved: dict[int, int] = {}
    unresolved: list[int] = []
    disagreeing: list[tuple[int, int, int]] = []
    for pk, direct_project_id, deployment_project_id in rows:
        if direct_project_id is None and deployment_project_id is None:
            unresolved.append(pk)
            continue
        if direct_project_id is None:
            resolved[pk] = deployment_project_id
            continue
        if deployment_project_id is not None and deployment_project_id != direct_project_id:
            disagreeing.append((pk, direct_project_id, deployment_project_id))
        resolved[pk] = direct_project_id

    target = label or model.__name__
    parent = f"{model.__name__} ({via})" if via else model.__name__
    missing = ids - set(resolved) - set(unresolved)
    if missing:
        raise ProjectScopeError(f"{target}: {model.__name__} {sorted(missing)[:IDS_TO_LOG]} not found.")
    if unresolved:
        raise ProjectScopeError(
            f"{target}: {model.__name__} {sorted(unresolved)[:IDS_TO_LOG]} have no project, "
            "directly or through their deployment."
        )
    if disagreeing:
        logger.warning(
            f"{target}: {len(disagreeing)} {parent} rows have a project that differs from their deployment's; "
            f"using their own. ({model.__name__} id, project, deployment project): {disagreeing[:IDS_TO_LOG]}"
        )
    return resolved


def _parents(model: type[models.Model]) -> list[tuple[models.ForeignKey, str]]:
    """Each target field of ``model`` with the path from its row to the project holder."""
    paths = getattr(model, "project_parent_paths", None) or (model.project_parent_path,)  # type: ignore[attr-defined]
    parents = []
    for path in paths:
        parent_name, _, via = path.partition("__")
        parents.append((model._meta.get_field(parent_name), via))
    return parents  # type: ignore[return-value]


def _set_parent(obj: Any, parents: list[tuple[models.ForeignKey, str]]) -> tuple[models.ForeignKey, str]:
    """The one target ``obj`` points at; a row with none or several cannot be scoped."""
    set_parents = [(field, via) for field, via in parents if getattr(obj, field.attname) is not None]
    if len(set_parents) != 1:
        names = ", ".join(field.name for field, _ in parents)
        raise ProjectScopeError(f"{type(obj).__name__}: a row must have exactly one of {names}.")
    return set_parents[0]


def fill_project_ids(objs: Iterable[Any]) -> None:
    """Set ``project_id`` on each unsaved row from its parent, in one query per kind of parent.

    Every row is filled, overwriting any value already set, so a writer cannot store a
    project other than its parent's. Rows must all be of one model.
    """
    objs = list(objs)
    if not objs:
        return
    model = type(objs[0])
    by_parent: dict[str, list[Any]] = {}
    parents = {field.name: (field, via) for field, via in _parents(model)}
    for obj in objs:
        field, _ = _set_parent(obj, list(parents.values()))
        by_parent.setdefault(field.name, []).append(obj)
    for name, rows in by_parent.items():
        parent_field, via = parents[name]
        parent_ids = {getattr(obj, parent_field.attname) for obj in rows}
        project_ids = project_ids_for(parent_field.related_model, parent_ids, via=via, label=model.__name__)
        for obj in rows:
            obj.project_id = project_ids[getattr(obj, parent_field.attname)]


def derived_project_expression(model: type[models.Model]) -> Coalesce:
    """The project a row of ``model`` should carry, as a database expression (see ``project_ids_for``).

    For a table with several targets, the unset targets join to nothing, so the one set
    target's project comes first.
    """
    expressions = []
    for parent_field, via in _parents(model):
        path = f"{parent_field.name}__{via}__" if via else f"{parent_field.name}__"
        expressions += [f"{path}project_id", f"{path}deployment__project_id"]
    return Coalesce(*expressions)


def project_scoped_models() -> list[type[models.Model]]:
    from django.apps import apps

    return [
        model
        for model in apps.get_models()
        if getattr(model, "project_parent_path", None) or getattr(model, "project_parent_paths", None)
    ]


def project_mismatch_counts() -> dict[str, int]:
    """For each project-scoped table, how many rows carry a project other than their parent's.

    Read-only; one COUNT per table. A row whose parent has no project at all counts as a mismatch.
    """
    # 0 stands in for "no project", which no row carries, so a NULL never hides a mismatch.
    return {
        model._meta.label: model.objects.order_by()
        .annotate(derived_project_id=Coalesce(derived_project_expression(model), models.Value(0)))
        .exclude(project_id=models.F("derived_project_id"))
        .count()
        for model in project_scoped_models()
    }
