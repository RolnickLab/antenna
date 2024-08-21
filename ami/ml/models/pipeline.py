import datetime
import logging
import typing
from urllib.parse import urljoin

import requests
from django.conf import settings
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

from ..schemas.v1 import PipelineRequest, PipelineResponse, SourceImageRequest
from ..schemas.v2 import (
    PipelineAsyncRequestData,
    PipelineAsyncRequestResponse,
    PipelineCallbackConfig,
    PipelineCallbackResponse,
    PipelineConfig,
)
from ..schemas.v2 import SourceImageRequest as SourceImageRequestAsync
from ..schemas.v2 import StageConfig
from .algorithm import Algorithm

logger = logging.getLogger(__name__)


class PipelineAsyncRequestStatus(models.TextChoices):
    """Status of a pipeline request."""

    SENT = "SENT", "Sent"
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    UNKNOWN = "UNKNOWN", "Unknown"


class PipelineAsyncRequestRecord(BaseModel):
    """A request record to an asynchronous pipeline backend."""

    pipeline_request_id = models.CharField(max_length=1024, null=True, blank=True)
    # endpoint_url = models.URLField()  # Doesn't work with docker hostnames
    endpoint_url = models.CharField(max_length=1024)
    token = models.CharField(max_length=1024)
    callback_url = models.CharField(max_length=1024)
    job = models.ForeignKey("jobs.Job", on_delete=models.SET_NULL, related_name="pipeline_requests", null=True)
    source_images = models.ManyToManyField(SourceImage, related_name="pipeline_requests")
    config_data = SchemaField(PipelineConfig, null=True, blank=True)
    response_data = SchemaField(PipelineCallbackResponse, null=True, blank=True)
    status = models.CharField(
        choices=PipelineAsyncRequestStatus.choices, default=PipelineAsyncRequestStatus.UNKNOWN, max_length=32
    )
    # last updated
    # status_data (if a status endpoint is created)

    def __str__(self):
        return f"PipelineAsyncRequest {self.pipeline_request_id} {self.status} {self.created_at}"

    def make_token(self):
        import secrets

        self.token = secrets.token_urlsafe(32)
        return self.token

    def save_results(self):
        if self.response_data:
            job_id = self.job.pk if self.job else None
            save_async_results(self.response_data, job_id=job_id)

    def save(self, *args, **kwargs):
        if not self.token:
            self.make_token()
        return super().save(*args, **kwargs)


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


def initiate_async_pipeline_request(
    pipeline: "Pipeline",
    endpoint_url: str,
    callback_url: str,
    images: typing.Iterable[SourceImage],
    job_id: int | None = None,
    pipeline_project_id: str = "ecos",
) -> PipelineAsyncRequestRecord:
    job = None
    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)

    pipeline_config = PipelineConfig(
        stages=[
            StageConfig(
                stage="OBJECT_DETECTION",
                stageImplementation="flatbug",
            ),
            StageConfig(
                stage="CLASSIFICATION",
                stageImplementation="mcc24",
            ),
        ]
    )

    request = PipelineAsyncRequestRecord.objects.create(
        job_id=job_id,
        endpoint_url=endpoint_url,
        config_data=pipeline_config,
        callback_url=callback_url,
    )
    request.source_images.set(images)
    if job:
        job.logger.info(f"Created async pipeline request {request} with {len(images)} images")

    # reverse the pipeline-callback URL in a context
    # where we have the request object to construct the absolute
    # public URL
    callback_config = PipelineCallbackConfig(
        callbackUrl=callback_url,
        callbackToken=request.token,
    )

    source_image_requests = [
        SourceImageRequestAsync(
            id=str(source_image.pk),
            url=source_image.public_url(),
            eventId=str(source_image.event.pk if source_image.event else ""),
        )
        for source_image in images
    ]

    # Construct and send the request
    request_data = PipelineAsyncRequestData(
        projectId=pipeline_project_id,
        jobId=str(job_id or ""),
        sourceImages=source_image_requests,
        callback=callback_config,
        pipelineConfig=pipeline_config,
    )
    logger.info(f"Sending async pipeline request to {endpoint_url}")
    logger.info(f"Async pipeline request data: {request_data}")

    # Add authorization header
    headers = {
        "Authorization": f"{pipeline.endpoint_token}",
    }
    resp = requests.post(endpoint_url, json=request_data.dict(), headers=headers)
    resp.raise_for_status()
    resp_data = PipelineAsyncRequestResponse(**resp.json())
    logger.info(f"INITIATED ASYNC PIPELINE REQUEST: {resp_data}")
    print(f"INITIATED ASYNC PIPELINE REQUEST: {resp_data}")
    request.pipeline_request_id = resp_data.requestId
    request.status = PipelineAsyncRequestStatus.SENT
    request.save()

    return request


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
        classifications = [classification for detection in detections for classification in detection.classifications]
        if len(detections):
            job.logger.info(f"Found {len(detections)} detections")
        if len(classifications):
            job.logger.info(f"Found {len(classifications)} classifications")

    return results


def _timestamp_to_datetime(timestamp: int) -> datetime.datetime:
    return now() + datetime.timedelta(seconds=timestamp)


def save_async_results(response: PipelineCallbackResponse, job_id: int | None = None):
    """
    Save results from an asynchronous ML pipeline API response.
    """
    created_objects = []
    job = None
    algorithms_used = set()
    source_images = set()
    results = response.data

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Saving results from async pipeline response: {response.pipelineRequestId}")

    for source_image_resp in results:
        source_image = SourceImage.objects.get(pk=source_image_resp.sourceImageId)
        source_images.add(source_image)

        stage_data = {str(stage.version): stage for stage in source_image_resp.stages}

        for detection_resp in source_image_resp.detections:
            stage_name = str(detection_resp.version)
            algorithm, _created = Algorithm.objects.get_or_create(name=stage_name)
            algorithms_used.add(algorithm)
            if _created:
                created_objects.append(algorithm)

            bbox = detection_resp.boundingBox
            existing_detection = Detection.objects.filter(
                source_image=source_image,
                bbox=[bbox.x1, bbox.y1, bbox.x2, bbox.y2],
                detection_algorithm=algorithm,
            ).first()
            if existing_detection:
                if not existing_detection.path:
                    existing_detection.path = detection_resp.cropUrl or ""
                    existing_detection.save()
                detection = existing_detection
            else:
                stage_info = stage_data.get(stage_name, None)
                timestamp = stage_info.timestamp if stage_info else None
                new_detection = Detection.objects.create(
                    source_image=source_image,
                    bbox=[bbox.x1, bbox.y1, bbox.x2, bbox.y2],
                    timestamp=source_image.timestamp,
                    path=detection_resp.cropUrl or "",
                    detection_time=timestamp,
                    detection_algorithm=algorithm,
                )
                new_detection.save()
                print("Created new detection", new_detection)
                created_objects.append(new_detection)
                detection = new_detection

            for classification in detection_resp.classifications:
                assert classification.algorithm, "No classification algorithm was specified in the returned results."
                classification_algo, _created = Algorithm.objects.get_or_create(
                    name=classification.algorithm,
                )
                algorithms_used.add(classification_algo)
                if _created:
                    created_objects.append(classification_algo)

                stage_info = stage_data.get(classification.algorithm, None)

                taxa_list, _created = TaxaList.objects.get_or_create(
                    name=f"Taxa returned by {classification_algo.name}",
                )
                if _created:
                    created_objects.append(taxa_list)

                label = classification.labelNames[0]
                score = classification.scores[0]
                taxon, _created = Taxon.objects.get_or_create(
                    name=label,
                    defaults={"name": label, "rank": TaxonRank.UNKNOWN},
                )
                if _created:
                    created_objects.append(taxon)

                taxa_list.taxa.add(taxon)

                new_classification = Classification()
                new_classification.detection = detection
                new_classification.taxon = taxon
                new_classification.algorithm = classification_algo
                new_classification.score = score

                if stage_info and stage_info.timestamp:
                    new_classification.timestamp = _timestamp_to_datetime(stage_info.timestamp)
                else:
                    new_classification.timestamp = now()
                created_objects.append(new_classification)

                if not detection.occurrence:
                    occurrence = Occurrence.objects.create(
                        event=source_image.event,
                        deployment=source_image.deployment,
                        project=source_image.project,
                        determination=taxon,
                        determination_score=score,
                    )
                    detection.occurrence = occurrence
                    detection.save()
                detection.occurrence.save()

                # Update precalculated counts on source images
                for source_image in source_images:
                    source_image.save()

    if job:
        if len(created_objects):
            job.logger.info(f"Created {len(created_objects)} objects")


def save_results(results: PipelineResponse, job_id: int | None = None) -> list[models.Model]:
    """
    Save results from ML pipeline API.

    @TODO break into task chunks.
    @TODO rewrite this
    """
    created_objects = []
    job = None

    pipeline, _created = Pipeline.objects.get_or_create(slug=results.pipeline, defaults={"name": results.pipeline})
    if _created:
        logger.warning(f"Pipeline choice returned by the ML backend was not recognized! {pipeline}")
        created_objects.append(pipeline)
    algorithms_used = set()

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
        if existing_detection:
            if not existing_detection.path:
                existing_detection.path = detection_resp.crop_image_url or ""
                existing_detection.save()
                print("Updated existing detection", existing_detection)
            detection = existing_detection
        else:
            new_detection = Detection.objects.create(
                source_image=source_image,
                bbox=list(detection_resp.bbox.dict().values()),
                timestamp=source_image.timestamp,
                path=detection_resp.crop_image_url or "",
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

            new_classification = Classification()
            new_classification.detection = detection
            new_classification.taxon = taxon
            new_classification.algorithm = classification_algo
            new_classification.score = max(classification.scores)
            new_classification.timestamp = now()  # @TODO get timestamp from API response
            # @TODO add reference to job or pipeline?

            new_classification.save()
            created_objects.append(new_classification)

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
                detection.occurrence = occurrence
                detection.save()
            detection.occurrence.save()

    # Update precalculated counts on source images
    for source_image in source_images:
        source_image.save()

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
    endpoint_token = models.CharField(max_length=255, null=True, blank=True)

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
            pipeline_choice=self.slug,
            images=images,
            job_id=job_id,
        )

    def get_callback_url(self):
        from rest_framework.reverse import reverse

        # Right now we only have one callback URL for all pipelines
        # @TODO add URL path kwargs for pipeline slug and job ID
        # Or put the pipeline request ID right in the URL?
        path = reverse("api:pipeline-callback")
        # @TODO get base URL from view request?
        base_url = settings.PUBLIC_BASE_URL

        callback_url = urljoin(base_url, path)
        return callback_url

    def process_images_async(
        self,
        images: typing.Iterable[SourceImage],
        job_id: int | None = None,
    ):
        if not self.endpoint_url:
            raise ValueError("No endpoint URL configured for this pipeline")
        return initiate_async_pipeline_request(
            endpoint_url=self.endpoint_url,
            pipeline=self,
            images=images,
            job_id=job_id,
            callback_url=self.get_callback_url(),
        )

    def save_results(self, *args, **kwargs):
        return save_results(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.slug:
            # @TODO slug may only need to be unique per project
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)
