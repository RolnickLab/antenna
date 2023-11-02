from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

from ami.main.admin import AdminBase

from .models import Job


@admin.register(Job)
class JobAdmin(AdminBase):
    """Admin panel example for ``Job`` model."""

    list_display = (
        "name",
        "status",
        "task_id",
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

    actions = [enqueue_jobs]

    exclude = (
        # This takes too long to load in the admin panel
        "source_image_single",
        # These are read-only fields
        "task_id",
        "scheduled_at",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
        "progress",
        "result",
    )
