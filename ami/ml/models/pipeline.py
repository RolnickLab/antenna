import typing

import pydantic
from django.db import models
from django_pydantic_field import SchemaField

from ami.base.models import BaseModel

from .algorithm import Algorithm


class PipelineStageParam(pydantic.BaseModel):
    name: str
    key: str
    value: typing.Any

    # Don't validate the value, since it can be anything
    class Config:
        validate_assignment = False


class PipelineStage(pydantic.BaseModel):
    """A configurable stage of a pipeline"""

    key: str
    name: str
    params: list[PipelineStageParam] = []

    class Config:
        validate_assignment = False


def default_stages() -> list[PipelineStage]:
    return [
        PipelineStage(
            key="default",
            name="Default Stage",
            params=[PipelineStageParam(name="Placeholder param", key="default", value=0)],
        )
    ]


@typing.final
class Pipeline(BaseModel):
    """A pipeline of algorithms"""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    version_name = models.CharField(max_length=255, blank=True)
    algorithms = models.ManyToManyField(Algorithm, related_name="pipelines")
    stages: list[PipelineStage] = SchemaField(default=default_stages)
    projects = models.ManyToManyField("main.Project", related_name="pipelines")

    class Meta:
        ordering = ["name", "version"]

        unique_together = [
            ["name", "version"],
        ]
