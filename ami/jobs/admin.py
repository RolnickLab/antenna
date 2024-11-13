from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

from ami.main.admin import AdminBase

from .models import Job, get_job_type_by_inferred_key


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
        "job_type_key",
        "inferred_job_type",
    )

    @admin.action()
    def enqueue_jobs(self, request: HttpRequest, queryset: QuerySet[Job]) -> None:
        for job in queryset:
            job.enqueue()
        self.message_user(request, f"Queued {queryset.count()} job(s).")

    @admin.display(description="Inferred Job Type")
    def inferred_job_type(self, obj: Job) -> str:
        """
        @TODO Remove this after running migration 0011_job_job_type_key.py and troubleshooting.
        """
        job_type = get_job_type_by_inferred_key(obj)
        return job_type.name if job_type else "Could not infer"

        # return obj.job_type().name

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
