from django.contrib import admin
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

from ami import tasks
from ami.labelstudio.models import LabelStudioConfig


@admin.register(LabelStudioConfig)
class LabelStudioConfigAdmin(admin.ModelAdmin):
    """Admin panel example for ``LabelStudioConfig`` model."""

    list_display = (
        "pk",
        "base_url",
        "task_collection",
        "active",
        "created_at",
        "updated_at",
    )

    @admin.action()
    def publish_tasks(self, request: HttpRequest, queryset: QuerySet[LabelStudioConfig]) -> None:
        # measure the time elapsed for the action
        for config in queryset:
            config.write_tasks()
        self.message_user(request, f"Tasks published for {queryset.count()} config(s).")

    @admin.action()
    def publish_tasks_async(self, request: HttpRequest, queryset: QuerySet[LabelStudioConfig]) -> None:
        # measure the time elapsed for the action
        queued_tasks = [tasks.write_tasks.apply_async([config.pk]) for config in queryset]
        self.message_user(
            request,
            f"Publishing tasks for {len(queued_tasks)} config(s) background tasks: {queued_tasks}.",
        )

    actions = [publish_tasks, publish_tasks_async]
