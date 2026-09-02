"""Shared admin-action machinery for triggering post-processing tasks.

Every post-processing task surfaces the same admin flow:

1. The operator selects rows and picks the action.
2. An intermediate confirmation page renders the task's knob form.
3. On submit, each row's config is validated against the task's pydantic
   ``config_schema`` and a Job is enqueued.

``make_post_processing_action`` builds the action callable for that flow so
each task only declares what varies: its task class, its knob form, and how a
selected row maps to a Job (scope + project + name). Tasks whose row→Job
mapping doesn't fit the default one-Job-per-row shape (e.g. partitioning events
across projects) pass their own ``build_jobs`` callable.

Validation lives in one place: the task's ``config_schema``. The knob form only
declares fields (label, help text, widget); it does not re-encode the schema's
rules. Schema errors raised while building Jobs are mapped back onto the form so
the operator sees them inline on the confirmation page.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

import pydantic
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Model
from django.db.models.query import QuerySet
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from ami.jobs.models import Job
from ami.ml.post_processing.admin.forms import BasePostProcessingActionForm
from ami.ml.post_processing.base import BasePostProcessingTask

logger = logging.getLogger(__name__)

CONFIRMATION_TEMPLATE = "admin/post_processing/confirmation.html"


class _ModelAdminProto(Protocol):
    """The slice of ``ModelAdmin`` the generic action touches."""

    model: type[Model]
    admin_site: Any

    def message_user(self, request: HttpRequest, message: str, level: Any = ..., **kwargs: Any) -> None:
        ...


class ConfigValidationErrors(Exception):
    """Raised by ``build_jobs`` when one or more rows produce invalid config.

    Carries ``(field_name_or_None, message)`` pairs so the caller can attach
    them to the knob form and re-render the confirmation page instead of
    creating any Jobs.
    """

    def __init__(self, errors: list[tuple[str | None, str]]):
        self.errors = errors
        super().__init__(f"{len(errors)} invalid config(s)")


def _schema_errors_to_form_fields(
    exc: pydantic.ValidationError,
    form_field_names: set[str],
) -> list[tuple[str | None, str]]:
    """Map a pydantic ``ValidationError`` onto form field names where possible.

    Errors on a field the form renders are attached to that field; everything
    else (e.g. an injected scope field) becomes a non-field error.
    """
    mapped: list[tuple[str | None, str]] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = str(loc[0]) if loc else None
        target = field if field in form_field_names else None
        mapped.append((target, err.get("msg", "Invalid value")))
    return mapped


def default_build_jobs(
    *,
    model_admin: _ModelAdminProto,
    request: HttpRequest,
    config: dict[str, Any],
    queryset: QuerySet,
    task_cls: type[BasePostProcessingTask],
    form_field_names: set[str],
    scope_resolver: Callable[[Any], dict[str, Any]],
    project_resolver: Callable[[Any], Any],
    name_resolver: Callable[[type[BasePostProcessingTask], Any], str],
) -> list[int]:
    """Validate every selected row, then enqueue one Job per row (all-or-nothing).

    Each row's full config is ``{**config, **scope_resolver(row)}`` validated
    against ``task_cls.config_schema``. If any row fails, nothing is created and
    ``ConfigValidationErrors`` is raised so the form can re-render with the
    errors inline.
    """
    validated: list[tuple[Any, pydantic.BaseModel]] = []
    errors: list[tuple[str | None, str]] = []

    for obj in queryset:
        full_config = {**config, **scope_resolver(obj)}
        try:
            validated.append((obj, task_cls.config_schema(**full_config)))
        except pydantic.ValidationError as exc:
            errors.extend(_schema_errors_to_form_fields(exc, form_field_names))

    if errors:
        raise ConfigValidationErrors(errors)

    # Create all Jobs in one transaction so the operation stays all-or-nothing even
    # if a create fails mid-loop. (Admin requests are already atomic via
    # ATOMIC_REQUESTS, but this helper may also be called outside a request — e.g. a
    # management command — where there's no ambient transaction.) Job.enqueue() uses
    # transaction.on_commit, so enqueues fire only once the block commits.
    job_pks: list[int] = []
    with transaction.atomic():
        for obj, model in validated:
            job = Job.objects.create(
                name=name_resolver(task_cls, obj),
                project=project_resolver(obj),
                job_type_key="post_processing",
                params={"task": task_cls.key, "config": model.dict()},
            )
            job.enqueue()
            job_pks.append(job.pk)
    return job_pks


def render_confirmation(
    model_admin: _ModelAdminProto,
    request: HttpRequest,
    queryset: QuerySet,
    *,
    task_cls: type[BasePostProcessingTask],
    form: BasePostProcessingActionForm,
    action_name: str,
    title: str,
    submit_label: str,
) -> TemplateResponse:
    """Render the shared intermediate confirmation page for ``task_cls``."""
    opts = model_admin.model._meta
    # Resolve the selection once; count from the materialized list (one query, not two).
    selected_pks = [str(pk) for pk in queryset.values_list("pk", flat=True)]
    return TemplateResponse(
        request,
        CONFIRMATION_TEMPLATE,
        {
            **model_admin.admin_site.each_context(request),
            "title": title,
            "task_label": task_cls.name,
            "form": form,
            "selected_count": len(selected_pks),
            "selected_pks": selected_pks,
            "action_name": action_name,
            "submit_label": submit_label,
            "changelist_url": reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist"),
            "model_meta": opts,
            "opts": opts,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


def _default_name_resolver(task_cls: type[BasePostProcessingTask], obj: Any) -> str:
    return f"Post-processing: {task_cls.name} on {obj._meta.verbose_name} {obj.pk}"


def make_post_processing_action(
    task_cls: type[BasePostProcessingTask],
    form_class: type[BasePostProcessingActionForm],
    *,
    scope_resolver: Callable[[Any], dict[str, Any]] | None = None,
    project_resolver: Callable[[Any], Any] = lambda obj: obj.project,
    name_resolver: Callable[[type[BasePostProcessingTask], Any], str] = _default_name_resolver,
    build_jobs: Callable[..., list[int]] | None = None,
    description: str | None = None,
    title: str | None = None,
    submit_label: str | None = None,
) -> Callable[[_ModelAdminProto, HttpRequest, QuerySet], HttpResponse | None]:
    """Build a Django admin action that triggers ``task_cls`` via the shared flow.

    Args:
        task_cls: the post-processing task. ``key``/``name``/``config_schema``
            drive the action name, labels, and config validation.
        form_class: the knob form rendered on the confirmation page.
        scope_resolver: maps a selected row to the config fields identifying its
            scope, e.g. ``lambda c: {"source_image_collection_id": c.pk}``.
            Required unless a custom ``build_jobs`` is supplied.
        project_resolver: maps a row to the Job's project (default ``obj.project``).
        name_resolver: maps ``(task_cls, row)`` to the Job name.
        build_jobs: escape hatch for tasks whose row→Job mapping isn't one
            Job per row (e.g. partitioning across projects). Receives the same
            keyword arguments as ``default_build_jobs`` and returns created Job
            pks; raise ``ConfigValidationErrors`` to re-render the form.
        description: admin action dropdown label.
        title / submit_label: confirmation-page heading and button text.

    The returned callable's ``__name__`` is ``run_<task key>`` so Django
    registers it under that name and the confirmation page's hidden ``action``
    field round-trips correctly.
    """
    if build_jobs is None and scope_resolver is None:
        raise ValueError("make_post_processing_action requires scope_resolver unless build_jobs is supplied")

    action_name = f"run_{task_cls.key}"
    resolved_title = title or f"Run {task_cls.name}"
    resolved_submit = submit_label or resolved_title
    resolved_description = description or f"Run {task_cls.name} post-processing task (async)"

    def action(
        model_admin: _ModelAdminProto,
        request: HttpRequest,
        queryset: QuerySet,
    ) -> HttpResponse | None:
        def _render(form: BasePostProcessingActionForm) -> TemplateResponse:
            return render_confirmation(
                model_admin,
                request,
                queryset,
                task_cls=task_cls,
                form=form,
                action_name=action_name,
                title=resolved_title,
                submit_label=resolved_submit,
            )

        # "Select all across pages" applies the action to the entire filtered
        # table rather than the rows the operator explicitly picked. Refuse it:
        # post-processing runs should act on a bounded, deliberately-selected set,
        # and rendering every matching pk as a hidden input would also overflow
        # POST size limits on a large table.
        if request.POST.get("select_across") == "1":
            model_admin.message_user(
                request,
                f'"Select all across pages" is not supported for {task_cls.name}. '
                "Select the specific rows you want to process.",
                level=messages.WARNING,
            )
            return None

        # Hand the form the selected rows so it can scope its fields to the
        # selection (e.g. only offer algorithms that ran on the chosen occurrence).
        if not request.POST.get("confirm"):
            return _render(form_class(scope_queryset=queryset))

        form = form_class(request.POST, scope_queryset=queryset)
        if not form.is_valid():
            return _render(form)

        runner = build_jobs or default_build_jobs
        kwargs: dict[str, Any] = dict(
            model_admin=model_admin,
            request=request,
            config=form.to_config(),
            queryset=queryset,
            task_cls=task_cls,
            form_field_names=set(form.fields),
            project_resolver=project_resolver,
            name_resolver=name_resolver,
        )
        # Only forward scope_resolver when set. A custom build_jobs supplied without
        # a scope_resolver should not receive a None it might try to call.
        if scope_resolver is not None:
            kwargs["scope_resolver"] = scope_resolver
        try:
            job_pks = runner(**kwargs)
        except ConfigValidationErrors as exc:
            for field, message in exc.errors:
                form.add_error(field, message)
            return _render(form)

        # Link each created Job to its admin change page so the operator can
        # follow progress and read any failure reason there. The admin URL is
        # used because it is always reachable from this admin action; the public
        # UI host is not reliably known in this context.
        job_links = format_html_join(
            ", ",
            '<a href="{}">Job {}</a>',
            ((request.build_absolute_uri(reverse("admin:jobs_job_change", args=[pk])), pk) for pk in job_pks),
        )
        model_admin.message_user(
            request,
            format_html(
                "Queued {} for {} {}(s). {}",
                task_cls.name,
                len(job_pks),
                model_admin.model._meta.verbose_name,
                job_links,
            ),
            level=messages.SUCCESS,
        )
        return None

    action.__name__ = action_name
    action.__qualname__ = action_name
    return admin.action(description=resolved_description)(action)
