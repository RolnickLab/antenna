import typing

from django.db import models

from ami.main.models import BaseModel

from .algorithms import Algorithm


@typing.final
class Pipeline(BaseModel):
    """A pipeline of algorithms"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=255, blank=True)
    algorithms = models.ManyToManyField(Algorithm, related_name="pipelines")
    stages = models.JSONField(null=True, blank=True)  # Order and parameters for each algorithm
