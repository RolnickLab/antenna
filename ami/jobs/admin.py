from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest

from ami.main.admin import AdminBase

from .models import DataExport, Job, get_job_type_by_inferred_key


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


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    """
    Admin panel for managing DataExport objects.
    """

    list_display = ("id", "user", "format", "status_display", "project", "created_at", "job")
    list_filter = ("format", "project")
    search_fields = ("user__username", "format", "project__name")
    readonly_fields = ("status_display", "file_url_display")

    fieldsets = (
        (
            None,
            {
                "fields": ("user", "format", "project", "filters", "job"),
            },
        ),
        (
            "Job Info",
            {
                "fields": ("status_display", "file_url_display"),
                "classes": ("collapse",),  # This makes job-related fields collapsible in the admin panel
            },
        ),
    )

    def get_queryset(self, request: HttpRequest):
        """
        Optimize queryset by selecting related project and job data.
        """
        return super().get_queryset(request).select_related("project", "job")

    @admin.display(description="Status")
    def status_display(self, obj):
        return obj.status  # Calls the @property from the model

    @admin.display(description="File URL")
    def file_url_display(self, obj):
        return obj.file_url  # Calls the @property from the model

    @admin.action(description="Run export job")
    def run_export_job(self, request: HttpRequest, queryset):
        """
        Admin action to trigger the export job manually.
        """
        for export in queryset:
            export.start_job()

        self.message_user(request, f"Started export job for {queryset.count()} export(s).")

    actions = [run_export_job]
