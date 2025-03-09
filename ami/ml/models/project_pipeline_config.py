import logging
import typing

from django.db import models

from ami.base.models import BaseModel
from ami.main.models import Project
from ami.ml.models.pipeline import Pipeline

logger = logging.getLogger(__name__)


@typing.final
class ProjectPipelineConfig(BaseModel):
    """Intermediate model to store the relationship between a project and a pipeline."""

    project = models.ForeignKey(Project, related_name="project_pipeline_configs", on_delete=models.CASCADE)
    pipeline = models.ForeignKey(Pipeline, related_name="project_pipeline_configs", on_delete=models.CASCADE)
    enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return f'#{self.pk} "{self.pipeline}" in {self.project}'

    class Meta:
        verbose_name = "Project-Pipeline Configuration"
        verbose_name_plural = "Project-Pipeline Configurations"
