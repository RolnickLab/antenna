from django.db import models
from django.utils.text import slugify

from ami.base.models import BaseModel
from ami.main.models import Project
from ami.users.models import User


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

    @property
    def status(self):
        return self.job.status if self.job else None

    def generate_filename(self):
        """Generates a slugified filename using project name and export ID."""
        from ami.exports.registry import ExportRegistry

        extension = ExportRegistry.get_exporter(self.format).file_format
        project_slug = slugify(self.project.name)  # Convert project name to a slug
        return f"{project_slug}_export-{self.id}.{extension}"
