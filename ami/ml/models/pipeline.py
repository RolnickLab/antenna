import logging
import typing

import requests
from django.db import models, transaction
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
    update_calculated_fields_for_events,
)
from ami.ml.tasks import celery_app, create_detection_images

from ..schemas import PipelineRequest, PipelineResponse, SourceImageRequest
from .algorithm import Algorithm

logger = logging.getLogger(__name__)


def filter_processed_images(
    images: typing.Iterable[SourceImage],
    pipeline: "Pipeline",
) -> typing.Iterable[SourceImage]:
    """
    Return only images that need to be processed by a given pipeline for the first time (have no detections)
    or have detections that need to be classified by the given pipeline.
    """
    pipeline_algorithms = pipeline.algorithms.all()

    for image in images:
        existing_detections = image.detections.filter(detection_algorithm__in=pipeline_algorithms)
        if not existing_detections.exists():
            logger.debug(f"Image {image} has no existing detections from pipeline {pipeline}")
            # If there are no existing detections from this pipeline, send the image
            yield image
        elif existing_detections.filter(classifications__isnull=True).exists():
            # Check if there are detections with no classifications
            logger.debug(f"Image {image} has existing detections with no classifications from pipeline {pipeline}")
            yield image
        else:
            # If there are existing detections with classifications,
            # Compare their classification algorithms to the current pipeline's algorithms
            detections_needing_classification = existing_detections.exclude(
                classifications__algorithm__in=pipeline_algorithms
            )
            if detections_needing_classification.exists():
                logger.debug(
                    f"Image {image} has existing detections that haven't been classified by the pipeline: {pipeline}"
                )
                logger.warn(
                    f"Image {image} has existing detections that haven't been classified by the pipeline: {pipeline} "
                    f"however we do yet have a mechanism to reclassify detections. Processing the image from scratch."
                )
                yield image
            else:
                # If all detections have been classified by the pipeline, skip the image
                logger.debug(
                    f"Image {image} has existing detections classified by the pipeline: {pipeline}, skipping!"
                )
                continue


def collect_images(
    collection: SourceImageCollection | None = None,
    source_images: list[SourceImage] | None = None,
    deployment: Deployment | None = None,
    job_id: int | None = None,
    pipeline: "Pipeline | None" = None,
    skip_processed: bool = True,
) -> typing.Iterable[SourceImage]:
    """
    Collect images from a collection, a list of images or a deployment.
    """
    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
    else:
        job = None

    # Set source to first argument that is not None
    if collection:
        images = collection.images.all()
    elif source_images:
        images = source_images
    elif deployment:
        images = SourceImage.objects.filter(deployment=deployment)
    else:
        raise ValueError("Must specify a collection, deployment or a list of images")

    total_images = len(images)
    if pipeline and skip_processed:
        msg = f"Filtering images that have already been processed by pipeline {pipeline}"
        logger.info(msg)
        if job:
            job.logger.info(msg)
        images = list(filter_processed_images(images, pipeline))
    else:
        msg = "NOT filtering images that have already been processed"
        logger.info(msg)
        if job:
            job.logger.info(msg)

    msg = f"Found {len(images)} out of {total_images} images to process"
    logger.info(msg)
    if job:
        job.logger.info(msg)

    return images


def process_images(
    pipeline: "Pipeline",
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
    task_logger = logger

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        task_logger = job.logger

    prefiltered_images = list(images)
    images = list(filter_processed_images(images=prefiltered_images, pipeline=pipeline))
    if len(images) < len(prefiltered_images):
        # Log how many images were filtered out because they have already been processed
        task_logger.info(f"Ignoring {len(prefiltered_images) - len(images)} images that have already been processed")

    if not images:
        task_logger.info("No images to process")
        return PipelineResponse(
            pipeline=pipeline.slug,
            source_images=[],
            detections=[],
            total_time=0,
        )
    task_logger.info(f"Sending {len(images)} images to ML backend {pipeline.slug}")
    urls = [source_image.public_url() for source_image in images if source_image.public_url()]

    request_data = PipelineRequest(
        pipeline=pipeline.slug,
        source_images=[
            SourceImageRequest(
                id=str(source_image.pk),
                url=url,
            )
            for source_image, url in zip(images, urls)
            if url
        ],
    )

    resp = requests.post(endpoint_url, json=request_data.dict())
    if not resp.ok:
        if job:
            try:
                msg = resp.json()["detail"]
            except Exception:
                msg = resp.content

            job.logger.error(msg)

        resp.raise_for_status()

    results = resp.json()
    results = PipelineResponse(**results)

    if job:
        job.logger.debug(f"Results: {results}")
        detections = results.detections
        classifications = [classification for detection in detections for classification in detection.classifications]
        if len(detections):
            job.logger.info(f"Found {len(detections)} detections")
        if len(classifications):
            job.logger.info(f"Found {len(classifications)} classifications")

    return results


@celery_app.task(soft_time_limit=60 * 4, time_limit=60 * 5)
def save_results(results: PipelineResponse | None = None, results_json: str | None = None, job_id: int | None = None):
    """
    Save results from ML pipeline API.

    @TODO break into task chunks.
    @TODO rewrite this!
    """
    created_objects = []
    job = None

    if results_json:
        results = PipelineResponse.parse_raw(results_json)
    assert results, "No results data passed to save_results task"

    pipeline, _created = Pipeline.objects.get_or_create(slug=results.pipeline, defaults={"name": results.pipeline})
    if _created:
        logger.warning(f"Pipeline choice returned by the ML backend was not recognized! {pipeline}")
        created_objects.append(pipeline)
    algorithms_used = set()

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        job.logger.info("Saving results...")

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

    for detection_resp in results.detections:
        # @TODO use bulk create, or optimize this in some way
        print(detection_resp)
        assert detection_resp.algorithm, "No detection algorithm was specified in the returned results."
        detection_algo, _created = Algorithm.objects.get_or_create(
            name=detection_resp.algorithm,
        )
        algorithms_used.add(detection_algo)
        if _created:
            created_objects.append(detection_algo)

        # @TODO hmmmm what to do
        source_image = SourceImage.objects.get(pk=detection_resp.source_image_id)
        source_images.add(source_image)
        existing_detection = Detection.objects.filter(
            source_image=source_image,
            detection_algorithm=detection_algo,
            bbox=list(detection_resp.bbox.dict().values()),
        ).first()
        # Ensure that the crop image URL is not empty or only a slash. None is fine.
        if detection_resp.crop_image_url and detection_resp.crop_image_url.strip("/"):
            crop_url = detection_resp.crop_image_url
        else:
            crop_url = None
        if existing_detection:
            if not existing_detection.path:
                existing_detection.path = crop_url
                existing_detection.save()
                print("Updated existing detection", existing_detection)
            detection = existing_detection
        else:
            new_detection = Detection.objects.create(
                source_image=source_image,
                bbox=list(detection_resp.bbox.dict().values()),
                timestamp=source_image.timestamp,
                path=crop_url,
                detection_time=detection_resp.timestamp,
                detection_algorithm=detection_algo,
            )
            new_detection.save()
            print("Created new detection", new_detection)
            created_objects.append(new_detection)
            detection = new_detection

        for classification in detection_resp.classifications:
            print(classification)

            assert classification.algorithm, "No classification algorithm was specified in the returned results."
            classification_algo, _created = Algorithm.objects.get_or_create(
                name=classification.algorithm,
            )
            algorithms_used.add(classification_algo)
            if _created:
                created_objects.append(classification_algo)

            taxa_list, _created = TaxaList.objects.get_or_create(
                name=f"Taxa returned by {classification_algo.name}",
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

            # @TODO this is asking for trouble
            # shouldn't we be able to get the detection from the classification?
            # also should filter by the correct detection algorithm
            # or do we use the bbox as a unique identifier?
            # then it doesn't matter what detection algorithm was used

            new_classification, created = Classification.objects.get_or_create(
                detection=detection,
                taxon=taxon,
                algorithm=classification_algo,
                score=max(classification.scores),
                defaults={"timestamp": classification.timestamp or now()},
            )

            if created:
                # Optionally add reference to job or pipeline here
                created_objects.append(new_classification)
            else:
                # Optionally handle the case where a duplicate is found
                logger.warn("Duplicate classification found, not creating a new one.")

            # Create a new occurrence for each detection (no tracking yet)
            # @TODO remove when we implement tracking
            if not detection.occurrence:
                occurrence = Occurrence.objects.create(
                    event=source_image.event,
                    deployment=source_image.deployment,
                    project=source_image.project,
                    determination=taxon,
                    determination_score=new_classification.score,
                )
                detection.occurrence = occurrence  # type: ignore
                detection.save()
            detection.occurrence.save()

    # Update precalculated counts on source images and events
    with transaction.atomic():
        for source_image in source_images:
            source_image.save()

    image_cropping_task = create_detection_images.delay(
        source_image_ids=[source_image.pk for source_image in source_images],
    )
    if job:
        job.logger.info(f"Creating detection images in sub-task {image_cropping_task.id}")

    event_ids = [img.event_id for img in source_images]
    update_calculated_fields_for_events(pks=event_ids)

    registered_algos = pipeline.algorithms.all()
    for algo in algorithms_used:
        # This is important for tracking what objects were processed by which algorithms
        # to avoid reprocessing, and for tracking provenance.
        if algo not in registered_algos:
            pipeline.algorithms.add(algo)
            logger.warning(f"Added unregistered algorithm {algo} to pipeline {pipeline}")

    if job:
        if len(created_objects):
            job.logger.info(f"Created {len(created_objects)} objects")
            try:
                previously_created = int(job.progress.get_stage_param("results", "objects_created").value)
                job.progress.update_stage(
                    "results",
                    objects_created=previously_created + len(created_objects),
                )
            except ValueError:
                pass
            else:
                job.update_progress()


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
    # @TODO the algorithms list be retrieved by querying the pipeline endpoint
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
        skip_processed: bool = True,
    ) -> typing.Iterable[SourceImage]:
        return collect_images(
            collection=collection,
            source_images=source_images,
            deployment=deployment,
            job_id=job_id,
            pipeline=self,
            skip_processed=skip_processed,
        )

    def process_images(self, images: typing.Iterable[SourceImage], job_id: int | None = None):
        if not self.endpoint_url:
            raise ValueError("No endpoint URL configured for this pipeline")
        return process_images(
            endpoint_url=self.endpoint_url,
            pipeline=self,
            images=images,
            job_id=job_id,
        )

    def save_results(self, results: PipelineResponse, job_id: int | None = None):
        return save_results(results=results, job_id=job_id)

    def save_results_async(self, results: PipelineResponse, job_id: int | None = None):
        # Returns an AsyncResult
        results_json = results.json()
        return save_results.delay(results_json=results_json, job_id=job_id)

    def save(self, *args, **kwargs):
        if not self.slug:
            # @TODO slug may only need to be unique per project
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)
