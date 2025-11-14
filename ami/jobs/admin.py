from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest

from ami.main.admin import AdminBase

from .models import Job


@admin.register(Job)
class JobAdmin(AdminBase):
    """Admin panel example for ``Job`` model."""

    list_display = (
        "name",
        "job_type_key",
        "status",
        "task_id",
        "project",
        "scheduled_at",
        "started_at",
        "finished_at",
        "duration",
    )

    @admin.action()
    def enqueue_jobs(self, request: HttpRequest, queryset: QuerySet[Job]) -> None:
        for job in queryset:
            job.enqueue()
        self.message_user(request, f"Queued {queryset.count()} job(s).")

    @admin.action()
    def retry_jobs(self, request: HttpRequest, queryset: QuerySet[Job]) -> None:
        for job in queryset:
            job.retry(async_task=True)
        self.message_user(request, f"Retried {queryset.count()} job(s).")

    @admin.action()
    def cancel_jobs(self, request: HttpRequest, queryset: QuerySet[Job]) -> None:
        for job in queryset:
            job.cancel()
        self.message_user(request, f"Cancelled {queryset.count()} job(s).")

    actions = [enqueue_jobs, retry_jobs]

    autocomplete_fields = (
        "source_image_collection",
        "source_image_single",
        "pipeline",
        "project",
    )

    readonly_fields = (
        "task_id",
        "scheduled_at",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
        "progress",
        "result",
    )

    list_filter = (
        "status",
        "job_type_key",
        "project",
        "source_image_collection",
        "pipeline",
    )
