from django.contrib import admin
from django.http import HttpRequest

from .models import DataExport


@admin.register(DataExport)
class DataExportAdmin(admin.ModelAdmin):
    """
    Admin panel for managing DataExport objects.
    """

    list_display = ("id", "user", "format", "status_display", "project", "created_at", "get_job")
    list_filter = ("format", "project")
    search_fields = ("user__username", "format", "project__name")
    readonly_fields = ("status_display", "file_url_display")

    fieldsets = (
        (
            None,
            {
                "fields": ("user", "format", "project", "filters"),
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

    @admin.display(description="Job ID")
    def get_job(self, obj):
        """Displays the related job ID or 'No Job' if none exists."""
        return obj.job.id if obj.job else "No Job"

    @admin.action(description="Run export job")
    def run_export_job(self, request: HttpRequest, queryset):
        """
        Admin action to trigger the export job manually.
        """
        for export in queryset:
            if export.job:
                export.job.enqueue()

        self.message_user(request, f"Started export job for {queryset.count()} export(s).")

    actions = [run_export_job]
