import logging

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.utils.functional import cached_property
from django.utils.text import slugify
from rest_framework.request import Request

from ami.base.models import BaseModel
from ami.main.models import Project
from ami.users.models import User

logger = logging.getLogger(__name__)


def get_export_choices():
    from ami.exports.registry import ExportRegistry

    """Dynamically fetch available export formats from the ExportRegistry."""
    return [(key, key) for key in ExportRegistry.get_supported_formats()]


class DataExport(BaseModel):
    """A model to track data exports"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exports")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="exports")
    format = models.CharField(max_length=255, choices=get_export_choices())
    filters = models.JSONField(null=True, blank=True)
    file_url = models.URLField(blank=True, null=True)
    # Number of exported records.
    record_count = models.PositiveIntegerField(default=0)
    # Size of the exported file in bytes.
    file_size = models.PositiveBigIntegerField(default=0)

    @cached_property
    def filters_display(self):
        """
        Cached property to generate a display-friendly version of filters.
        """
        from django.apps import apps

        related_models = {
            "collection": "main.SourceImageCollection",
            "taxa_list": "main.TaxaList",
        }
        filters = self.filters or {}
        filters_display = {}

        for key, value in filters.items():
            if key in related_models:
                model_path = related_models[key]
                try:
                    Model = apps.get_model(model_path)
                    instance = Model.objects.get(pk=value)
                    filters_display[key] = {"id": value, "name": str(instance)}
                except Model.DoesNotExist:
                    filters_display[key] = {"id": value, "name": f"{model_path} with id {value} not found"}
                except Exception as e:
                    filters_display[key] = {"id": value, "name": f"Error: {str(e)}"}
            else:
                filters_display[key] = value

        return filters_display

    def generate_filename(self):
        """Generates a slugified filename using project name and export ID."""
        from ami.exports.registry import ExportRegistry

        extension = ExportRegistry.get_exporter(self.format).file_format
        project_slug = slugify(self.project.name)  # Convert project name to a slug
        return f"{project_slug}_export-{self.pk}.{extension}"

    def save_export_file(self, file_temp_path):
        """
        Saves the exported file to the default storage.
        """
        # Generate file path in the 'exports' directory
        file_path = f"exports/{self.generate_filename()}"

        # Save the file to the specified path in default storage
        with open(file_temp_path, "rb") as f:
            default_storage.save(file_path, f)
        file_url = f"{settings.MEDIA_URL}{file_path}"
        return file_url

    def run_export(self):
        from ami.exports.registry import ExportRegistry

        export_format = self.format
        export_class = ExportRegistry.get_exporter(export_format)
        if not export_class:
            raise ValueError("Invalid export format")
        logger.debug(f"Exporter class {export_class}")
        exporter = export_class(self)
        logger.info(f"Starting export for format: {export_format}")
        file_temp_path = exporter.export()
        file_url = self.save_export_file(file_temp_path)
        self.file_url = file_url
        self.save()
        return file_url

    def get_absolute_url(self, request: Request | None) -> str | None:
        """Returns the full URL of the file."""
        if not self.file_url:
            return None
        if not request:
            return self.file_url
        else:
            return request.build_absolute_uri(self.file_url)
