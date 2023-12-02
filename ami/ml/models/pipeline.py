import typing

import requests
from django.db import models
from django.utils.text import slugify
from django.utils.timezone import now
from django_pydantic_field import SchemaField
from rich import print

from ami.base.models import BaseModel
from ami.base.schemas import ConfigurableStage, default_stages
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Occurrence,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
)

from ..schemas import PipelineRequest, PipelineResponse, SourceImageRequest
from .algorithm import Algorithm


def collect_images(
    collection: SourceImageCollection | None = None,
    source_images: list[SourceImage] | None = None,
    deployment: Deployment | None = None,
    job_id: int | None = None,
) -> typing.Iterable[SourceImage]:
    """
    Collect images from a collection, a list of images or a deployment.
    """
    # Set source to first argument that is not None
    if collection:
        images = collection.images.all()
    elif source_images:
        images = source_images
    elif deployment:
        images = SourceImage.objects.filter(deployment=deployment)
    else:
        raise ValueError("Must specify a collection, deployment or a list of images")

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Found {len(images)} images to process")

    return images


def process_images(
    pipeline_choice: str,
    endpoint_url: str,
    images: typing.Iterable[SourceImage],
    job_id: int | None = None,
) -> PipelineResponse:
    """
    Process images using ML pipeline API.

    @TODO find a home for this function.
    @TODO break into task chunks.
    """
    job = None
    images = list(images)

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Sending {len(images)} images to ML backend {pipeline_choice}")

    request_data = PipelineRequest(
        pipeline=pipeline_choice,  # type: ignore
        source_images=[
            SourceImageRequest(
                id=str(source_image.pk),
                url=source_image.public_url(),
            )
            for source_image in images
        ],
    )

    resp = requests.post(endpoint_url, json=request_data.dict())
    resp.raise_for_status()
    results = resp.json()
    results = PipelineResponse(**results)

    if job:
        job.logger.debug(f"Results: {results}")
        detections = results.detections
        classifications = results.classifications
        if len(detections):
            job.logger.info(f"Found {len(detections)} detections")
        if len(classifications):
            job.logger.info(f"Found {len(classifications)} classifications")

    return results


def save_results(results: PipelineResponse, job_id: int | None = None) -> list[models.Model]:
    """
    Save results from ML pipeline API.

    @TODO break into task chunks.
    @TODO rewrite this
    """
    created_objects = []
    job = None

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        job.logger.info("Saving results")

    # collection_name = f"Images processed by {results.pipeline} pipeline"
    # if job_id:
    #     from ami.jobs.models import Job

    #     job = Job.objects.get(pk=job_id)
    #     collection_name = f"Images processed by {results.pipeline} pipeline for job {job.name}"

    # collection = SourceImageCollection.objects.create(name=collection_name)
    # source_image_ids = [source_image.id for source_image in results.source_images]
    # source_images = SourceImage.objects.filter(pk__in=source_image_ids)
    # collection.images.set(source_images)
    source_images = set()

    for detection in results.detections:
        print(detection)
        assert detection.algorithm
        algo, _created = Algorithm.objects.get_or_create(
            name=detection.algorithm,
        )
        # @TODO hmmmm what to do
        source_image = SourceImage.objects.get(pk=detection.source_image_id)
        source_images.add(source_image)
        existing_detection = Detection.objects.filter(
            source_image=source_image,
            bbox=list(detection.bbox.dict().values()),
        ).first()
        if existing_detection:
            if not existing_detection.path:
                existing_detection.path = detection.crop_image_url or ""
                existing_detection.save()
                print("Updated existing detection", existing_detection)
        else:
            new_detection = Detection.objects.create(
                source_image=source_image,
                bbox=list(detection.bbox.dict().values()),
                path=detection.crop_image_url or "",
                detection_time=detection.timestamp,
            )
            new_detection.detection_algorithm = algo
            # new_detection.detection_time = detection.inference_time
            new_detection.timestamp = now()  # @TODO what is this field for
            new_detection.save()
            print("Created new detection", new_detection)
            created_objects.append(new_detection)

    for classification in results.classifications:
        print(classification)
        source_image = SourceImage.objects.get(pk=classification.source_image_id)
        source_images.add(source_image)

        assert classification.algorithm
        algo, _created = Algorithm.objects.get_or_create(
            name=classification.algorithm,
        )
        if _created:
            created_objects.append(algo)

        taxa_list, _created = TaxaList.objects.get_or_create(
            name=f"Taxa returned by {algo.name}",
        )
        if _created:
            created_objects.append(taxa_list)

        taxon, _created = Taxon.objects.get_or_create(
            name=classification.classification,
            defaults={"name": classification.classification, "rank": TaxonRank.UNKNOWN},
        )
        if _created:
            created_objects.append(taxon)

        taxa_list.taxa.add(taxon)

        detection = Detection.objects.filter(
            source_image=source_image,
            bbox=list(classification.bbox.dict().values()),
        ).first()
        assert detection

        new_classification = Classification()
        new_classification.detection = detection
        new_classification.taxon = taxon
        new_classification.algorithm = algo
        new_classification.score = classification.scores[0]
        new_classification.timestamp = now()  # @TODO get timestamp from API response
        # @TODO add reference to job or pipeline?

        new_classification.save()
        created_objects.append(new_classification)

        # Create a new occurrence for each detection (no tracking yet)
        if not detection.occurrence:
            occurrence = Occurrence.objects.create(
                event=source_image.event,
                deployment=source_image.deployment,
                project=source_image.project,
                determination=taxon,
            )
            detection.occurrence = occurrence
            detection.save()

    # Update precalculated counts on source images
    for source_image in source_images:
        source_image.save()

    if job:
        if len(created_objects):
            job.logger.info(f"Created {len(created_objects)} objects")

    return created_objects


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

    def collect_images(
        self,
        collection: SourceImageCollection | None = None,
        source_images: list[SourceImage] | None = None,
        deployment: Deployment | None = None,
        job_id: int | None = None,
    ) -> typing.Iterable[SourceImage]:
        return collect_images(
            collection=collection,
            source_images=source_images,
            deployment=deployment,
            job_id=job_id,
        )

    def process_images(self, images: typing.Iterable[SourceImage], job_id: int | None = None):
        if not self.endpoint_url:
            raise ValueError("No endpoint URL configured for this pipeline")
        return process_images(
            endpoint_url=self.endpoint_url,
            pipeline_choice=self.slug,
            images=images,
            job_id=job_id,
        )

    def save_results(self, *args, **kwargs):
        return save_results(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.slug:
            # @TODO slug may only need to be unique per project
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)
