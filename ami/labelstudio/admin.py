from django.contrib import admin

from ami.labelstudio.models import LabelStudioConfig
from ami.labelstudio.views import (
    populate_binary_classification_tasks,
    populate_object_detection_tasks,
    populate_species_classification_tasks,
)


@admin.action(description="Populate Label Studio Tasks")
def populate_label_studio_tasks(modeladmin, request, queryset):
    """Sync Label Studio tasks."""
    populate_object_detection_tasks()
    populate_binary_classification_tasks()
    populate_species_classification_tasks()


@admin.register(LabelStudioConfig)
class LabelStudioConfigAdmin(admin.ModelAdmin):
    """Admin panel example for ``LabelStudioConfig`` model."""

    list_display = (
        "pk",
        "sync_active",
        "object_detection_project_id",
        "binary_classification_project_id",
        "species_classification_project_id",
        "updated_at",
    )

    actions = [populate_label_studio_tasks]
