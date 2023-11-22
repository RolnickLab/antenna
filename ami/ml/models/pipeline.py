import typing

from django.db import models
from django.utils.text import slugify
from django_pydantic_field import SchemaField
from rich import print

from ami.base.models import BaseModel
from ami.base.schemas import ConfigurableStage, default_stages
from ami.main.models import SourceImage, SourceImageCollection

from ..schemas import PipelineRequest, PipelineResponse, SourceImageRequest
from .algorithm import Algorithm


def process_images(
    pipeline_choice: str,
    endpoint_url: str,
    collection: SourceImageCollection | None = None,
    source_images: list[SourceImage] | None = None,
) -> PipelineResponse:
    """
    Process images using ML pipeline API.

    @TODO find a home for this function.
    @TODO break into task chunks.
    """
    import requests

    if collection:
        images = collection.images.all()
    elif source_images:
        images = source_images
    else:
        raise ValueError("Must provide either a collection or a list of images")

    request_data = PipelineRequest(
        pipeline=pipeline_choice,  # @TODO validate pipeline_choice # type: ignore
        source_images=[
            SourceImageRequest(
                id=str(source_image.pk),
                url=source_image.public_url(),
            )
            for source_image in images
        ],
    )

    resp = requests.post(endpoint_url, json=request_data.dict())
    resp.raise_for_status
    results = resp.json()
    results = PipelineResponse(**results)
    print("Processing results from ML endpoint", results)
    return results


class PipelineStage(ConfigurableStage):
    """A configurable stage of a pipeline."""


@typing.final
class Pipeline(BaseModel):
    """A pipeline of algorithms"""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    version_name = models.CharField(max_length=255, blank=True)
    algorithms = models.ManyToManyField(Algorithm, related_name="pipelines")
    stages: list[PipelineStage] = SchemaField(
        default=default_stages,
        help_text=(
            "The stages of the pipeline. This is mainly for display. "
            "The backend implementation of the pipeline may process data in any way."
        ),
    )
    projects = models.ManyToManyField("main.Project", related_name="pipelines")
    endpoint_url = models.URLField(null=True, blank=True)

    class Meta:
        ordering = ["name", "version"]

        unique_together = [
            ["name", "version"],
        ]

    def process_images(self, *args, **kwargs):
        if not self.endpoint_url:
            raise ValueError("No endpoint URL configured for this pipeline")
        return process_images(
            endpoint_url=self.endpoint_url,
            pipeline_choice=self.slug,
            *args,
            **kwargs,
        )

    def save(self, *args, **kwargs):
        if not self.slug:
            # @TODO slug may only need to be unique per project
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)
