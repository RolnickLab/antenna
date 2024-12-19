import collections
import logging
import time
import typing

import requests
from django.db import models, transaction
from django.utils.text import slugify
from django.utils.timezone import now
from django_pydantic_field import SchemaField

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
from ami.ml.models.algorithm import Algorithm, AlgorithmCategoryMap
from ami.ml.schemas import (
    AlgorithmResponse,
    ClassificationResponse,
    DetectionResponse,
    PipelineRequest,
    PipelineResponse,
    SourceImageRequest,
)
from ami.ml.tasks import celery_app, create_detection_images

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
            logger.debug(f"Image {image} needs processing: has no existing detections from pipeline's detector")
            # If there are no existing detections from this pipeline, send the image
            yield image
        elif existing_detections.filter(classifications__isnull=True).exists():
            # Check if there are detections with no classifications
            logger.debug(
                f"Image {image} needs processing: has existing detections with no classifications "
                "from pipeline {pipeline}"
            )
            yield image
        else:
            # If there are existing detections with classifications,
            # Compare their classification algorithms to the current pipeline's algorithms
            pipeline_algorithm_ids = pipeline_algorithms.values_list("id", flat=True)
            detection_algorithm_ids = existing_detections.values_list("classifications__algorithm_id", flat=True)

            if not set(pipeline_algorithm_ids).issubset(set(detection_algorithm_ids)):
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
        try:
            msg = resp.json()["detail"]
        except Exception:
            msg = resp.content
        if job:
            job.logger.error(msg)
        else:
            logger.error(msg)

        resp.raise_for_status()

    results = resp.json()
    results = PipelineResponse(**results)

    if job:
        job.logger.debug(f"Results: {results}")
        detections = results.detections
        classifications = [classification for detection in detections for classification in detection.classifications]
        job.logger.info(
            f"Pipeline results returned {len(results.source_images)} images, {len(detections)} detections, "
            f"{len(classifications)} classifications"
        )

    return results


def create_algorithms_and_category_map(
    algorithms_data: typing.Mapping[str, AlgorithmResponse],
    logger: logging.Logger = logger,
) -> dict[str, Algorithm]:
    """
    Create algorithms and category maps from a PipelineResponse.

    :param algorithms: A dictionary of algorithms from the pipeline response
    :param created_objects: A list to store created objects

    :return: A dictionary of algorithms used in the pipeline, keyed by the algorithm key

    @TODO this should be called when registering a pipeline, not when saving results.
    But currently we don't have a way to register pipelines.
    """
    algorithms_used: dict[str, Algorithm] = {}
    for algorithm_data in algorithms_data.values():
        category_map = None
        category_map_data = algorithm_data.category_map
        if category_map_data:
            labels_hash = AlgorithmCategoryMap.make_labels_hash(category_map_data.labels)
            category_map, _created = AlgorithmCategoryMap.objects.get_or_create(
                # @TODO this is creating a new category map every time
                # Will create a new category map if the labels are different
                labels_hash=labels_hash,
                version=category_map_data.version,
                defaults={
                    "data": category_map_data.data,
                    "labels": category_map_data.labels,
                    "description": category_map_data.description,
                    "uri": category_map_data.uri,
                },
            )
            if _created:
                logger.info(f"Registered new category map {category_map}")
            else:
                logger.info(f"Assigned existing category map {category_map}")
        else:
            logger.warning(
                f"No category map found for algorithm {algorithm_data.key} in response."
                " Will attempt to create one from the classification results."
            )

        algo, _created = Algorithm.objects.get_or_create(
            key=algorithm_data.key,
            defaults={
                "name": algorithm_data.name,
                "task_type": algorithm_data.task_type,
                "version": algorithm_data.version,
                "version_name": algorithm_data.version_name,
                "uri": algorithm_data.uri,
                "category_map": category_map or None,
            },
        )

        if not algo.category_map or len(algo.category_map.data) == 0:
            # Update existing algorithm that is missing a category map
            algo.category_map = category_map
            algo.save()

        algorithms_used[algo.key] = algo

        if _created:
            logger.info(f"Registered new algorithm {algo}")
        else:
            logger.info(f"Assigned algorithm {algo}")

    return algorithms_used


def get_or_create_detection(
    source_image: SourceImage,
    detection_resp: DetectionResponse,
    algorithms_used: dict[str, Algorithm],
    save: bool = True,
    logger: logging.Logger = logger,
) -> tuple[Detection, bool]:
    """
    Create a Detection object from a DetectionResponse, or update an existing one.

    :param detection_resp: A DetectionResponse object
    :param algorithms_used: A dictionary of algorithms used in the pipeline, keyed by the algorithm key
    :param created_objects: A list to store created objects

    :return: A tuple of the Detection object and a boolean indicating whether it was created
    """
    serialized_bbox = list(detection_resp.bbox.dict().values())
    detection_repr = f"Detection {detection_resp.source_image_id} {serialized_bbox}"

    assert detection_resp.algorithm, f"No detection algorithm was specified for detection {detection_repr}"
    detection_algo = algorithms_used[detection_resp.algorithm.key]

    assert str(detection_resp.source_image_id) == str(
        source_image.pk
    ), f"Detection belongs to a different source image: {detection_repr}"

    existing_detection = Detection.objects.filter(
        source_image=source_image,
        detection_algorithm=detection_algo,
        bbox=serialized_bbox,
    ).first()

    # A detection may have a pre-existing crop image URL or not.
    # If not, a new one will be created in a periodic background task.
    if detection_resp.crop_image_url and detection_resp.crop_image_url.strip("/"):
        # Ensure that the crop image URL is not empty or only a slash. None is fine.
        crop_url = detection_resp.crop_image_url
    else:
        crop_url = None

    if existing_detection:
        if not existing_detection.path:
            existing_detection.path = crop_url
            existing_detection.save()
            logger.debug(f"Updated crop_url of existing detection {existing_detection}")
        detection = existing_detection

    else:
        new_detection = Detection(
            source_image=source_image,
            bbox=serialized_bbox,
            timestamp=source_image.timestamp,
            path=crop_url,
            detection_time=detection_resp.timestamp,
            detection_algorithm=detection_algo,
        )
        if save:
            new_detection.save()
            logger.debug(f"Created new detection {new_detection}")
        else:
            logger.debug(f"Initialized new detection {new_detection} (not saved)")

        detection = new_detection

    created = not existing_detection
    return detection, created


def create_detections(
    detections: list[DetectionResponse],
    algorithms_used: dict[str, Algorithm],
    logger: logging.Logger = logger,
) -> list[Detection]:
    """
    Efficiently create multiple Detection objects from a list of DetectionResponse objects, grouped by source image.
    Using bulk create.

    :param detections: A list of DetectionResponse objects
    :param algorithms_used: A dictionary of algorithms used in the pipeline, keyed by the algorithm key
    :param created_objects: A list to store created objects

    :return: A list of Detection objects
    """
    source_image_ids = {detection.source_image_id for detection in detections}
    source_images = SourceImage.objects.filter(pk__in=source_image_ids)
    source_image_map = {str(source_image.pk): source_image for source_image in source_images}

    existing_detections: list[Detection] = []
    new_detections: list[Detection] = []
    for detection_resp in detections:
        source_image = source_image_map.get(detection_resp.source_image_id)
        if not source_image:
            logger.error(f"Source image {detection_resp.source_image_id} not found, skipping Detection creation")
            continue

        detection, created = get_or_create_detection(
            source_image=source_image,
            detection_resp=detection_resp,
            algorithms_used=algorithms_used,
            save=False,
            logger=logger,
        )
        if created:
            new_detections.append(detection)
        else:
            existing_detections.append(detection)

    Detection.objects.bulk_create(new_detections)
    # logger.info(f"Created {len(new_detections)} new detections for {len(source_image_ids)} source image(s)")
    logger.info(
        f"Created {len(new_detections)} new detections, updated {len(existing_detections)} existing detections, "
        f"for {len(source_image_ids)} source image(s)"
    )

    return existing_detections + new_detections


def create_category_map_for_classification(
    classification_resp: ClassificationResponse,
    logger: logging.Logger = logger,
) -> AlgorithmCategoryMap:
    """
    Create a simple category map from a ClassificationResponse.
    The complete category map should be created when registering the algorithm before processing images.

    :param classification: A ClassificationResponse object

    :return: The AlgorithmCategoryMap object
    """
    labels = classification_resp.labels or list(map(str, range(len(classification_resp.scores))))
    category_map_data = [
        {
            "label": label,
            "index": i,
        }
        for i, label in enumerate(labels)
    ]
    logger.info(f"Creating placeholder category map with data: {category_map_data}")
    category_map = AlgorithmCategoryMap.objects.create(
        data=category_map_data,
        version=classification_resp.timestamp.isoformat(),
        description="Placeholder category map automatically created from classification data",
        labels=labels,
    )
    return category_map


def get_or_create_taxon_for_classification(
    algorithm: Algorithm,
    classification_resp: ClassificationResponse,
    logger: logging.Logger = logger,
) -> Taxon:
    """
    Create a Taxon object from a ClassificationResponse and add it to a TaxaList.

    :param classification: A ClassificationResponse object

    :return: The Taxon object
    """
    taxa_list, _created = TaxaList.objects.get_or_create(
        name=f"Taxa returned by {algorithm.name}",
    )
    if _created:
        logger.info(f"Created new taxa list {taxa_list}")
    else:
        logger.debug(f"Using existing taxa list {taxa_list}")

    # Get top label from classification scores
    assert algorithm.category_map, f"No category map found for algorithm {algorithm}"
    label_data: dict = algorithm.category_map.data[classification_resp.scores.index(max(classification_resp.scores))]
    taxon, _created = Taxon.objects.get_or_create(
        name=classification_resp.classification,
        defaults={
            "name": classification_resp.classification,
            "rank": label_data.get("taxon_rank", TaxonRank.UNKNOWN),
        },
    )
    if _created:
        logger.info(f"Registered new taxon {taxon}")

    taxa_list.taxa.add(taxon)
    return taxon


def create_classification(
    detection: Detection,
    classification_resp: ClassificationResponse,
    algorithms_used: dict[str, Algorithm],
    save: bool = True,
    logger: logging.Logger = logger,
) -> tuple[Classification, bool]:
    """
    Create a Classification object from a ClassificationResponse, or update an existing one.

    :param detection: A Detection object
    :param classification: A ClassificationResponse object
    :param algorithms_used: A dictionary of algorithms used in the pipeline, keyed by the algorithm key
    :param created_objects: A list to store created objects

    :return: A tuple of the Classification object and a boolean indicating whether it was created
    """
    assert (
        classification_resp.algorithm
    ), f"No classification algorithm was specified for classification {classification_resp}"
    logger.debug(f"Processing classification {classification_resp}")

    classification_algo = algorithms_used[classification_resp.algorithm.key]

    if not classification_algo.category_map:
        logger.warning(
            f"Classification algorithm {classification_algo} "
            "has no category map! "
            "Creating one from data in the first classification if possible."
        )
        category_map = create_category_map_for_classification(classification_resp, logger=logger)
        classification_algo.category_map = category_map
        classification_algo.save()
        classification_algo.refresh_from_db()

    taxon = get_or_create_taxon_for_classification(
        algorithm=classification_algo,
        classification_resp=classification_resp,
        logger=logger,
    )

    existing_classification = Classification.objects.filter(
        detection=detection,
        taxon=taxon,
        algorithm=classification_algo,
        score=max(classification_resp.scores),
    ).first()

    if existing_classification:
        logger.debug(
            "Duplicate classification found: "
            f"{existing_classification.taxon} from {existing_classification.algorithm}, "
            "not creating a new one."
        )
        fields_to_update = []
        for field in ["logits", "scores", "terminal"]:
            # update new fields if they are None
            if getattr(existing_classification, field) is None:
                fields_to_update.append(field)
        if fields_to_update:
            logger.info(f"Updating fields {fields_to_update} for existing classification {existing_classification}")
            for field in fields_to_update:
                setattr(existing_classification, field, getattr(classification_resp, field))
            existing_classification.save(update_fields=fields_to_update)
            logger.info(f"Updated existing classification {existing_classification}")

        classification = existing_classification

    else:
        new_classification = Classification(
            detection=detection,
            taxon=taxon,
            algorithm=classification_algo,
            score=max(classification_resp.scores),
            timestamp=classification_resp.timestamp or now(),
            logits=classification_resp.logits,
            scores=classification_resp.scores,
            terminal=classification_resp.terminal,
        )
        classification = new_classification

        if save:
            new_classification.save()
            logger.debug(f"Created new classification {new_classification}")
        else:
            logger.debug(f"Initialized new classification {new_classification} (not saved)")

    return classification, not existing_classification


def create_classifications(
    detections: list[Detection],
    detection_responses: list[DetectionResponse],
    algorithms_used: dict[str, Algorithm],
    logger: logging.Logger = logger,
    save: bool = True,
) -> list[Classification]:
    """
    Efficiently create multiple Classification objects from a list of ClassificationResponse objects,
    grouped by detection.

    :param detection: A Detection object
    :param classifications: A list of ClassificationResponse objects
    :param algorithms_used: A dictionary of algorithms used in the pipeline, keyed by the algorithm key

    :return: A list of Classification objects

    @TODO bulk create all classifications for all detections in request
    """
    existing_classifications: list[Classification] = []
    new_classifications: list[Classification] = []

    for detection, detection_resp in zip(detections, detection_responses):
        for classification_resp in detection_resp.classifications:
            classification, created = create_classification(
                detection=detection,
                classification_resp=classification_resp,
                algorithms_used=algorithms_used,
                save=False,
                logger=logger,
            )
            if created:
                new_classifications.append(classification)
            else:
                # @TODO consider adding logits, scores and terminal state to existing classifications (new fields)
                existing_classifications.append(classification)

    Classification.objects.bulk_create(new_classifications)
    logger.info(
        f"Created {len(new_classifications)} new classifications, updated {len(existing_classifications)} existing "
        f"classifications for detection {detection}"
    )

    return existing_classifications + new_classifications


def create_occurrence_for_detection(
    detection: Detection,
    classifications: list[Classification],
    logger: logging.Logger = logger,
) -> Occurrence:
    """
    Create an Occurrence object from a Detection and a list of Classification objects.

    Select the best terminal classification for the occurrence determination.

    :param detection: A Detection object
    :param classifications: A list of Classification objects

    :return: The Occurrence object
    """

    terminal_classifications = [c for c in classifications if c.terminal]
    if not terminal_classifications:
        logger.warning(
            f"No terminal classification found for detection {detection}. " "Using intermediates if available."
        )
        terminal_classifications = classifications

    best_classification = max(terminal_classifications, key=lambda c: c.score or float("-inf"))

    if not detection.occurrence:
        occurrence = Occurrence.objects.create(
            event=detection.source_image.event,
            deployment=detection.source_image.deployment,
            project=detection.source_image.project,
            determination=best_classification.taxon,
            determination_score=best_classification.score,
        )
        occurrence.save()  # Ensure any signals are triggered
        logger.info(f"Created new occurrence {occurrence} for detection {detection}")
        detection.occurrence = occurrence  # type: ignore
        detection.save()

    return detection.occurrence


@celery_app.task(soft_time_limit=60 * 4, time_limit=60 * 5)
def save_results(
    results: PipelineResponse | None = None,
    results_json: str | None = None,
    job_id: int | None = None,
    return_created=False,
):
    """
    Save results from ML pipeline API.

    @TODO Continue improving bulk create. Group everything / all loops by source image.
    """
    job = None
    job_logger = logger
    start_time = time.time()

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        job_logger = job.logger

    if results_json:
        results = PipelineResponse.parse_raw(results_json)
    assert results, "No results data passed to save_results task"
    job_logger.info(f"Saving results from pipeline {results.pipeline}")

    results = PipelineResponse.parse_obj(results.dict())
    source_images = SourceImage.objects.filter(pk__in=[int(img.id) for img in results.source_images]).distinct()

    pipeline, _created = Pipeline.objects.get_or_create(slug=results.pipeline, defaults={"name": results.pipeline})
    if _created:
        job_logger.warning(
            f"The pipeline returned by the ML backend was not recognized, created a placeholder: {pipeline}"
        )

    # Create algorithms and category maps
    algorithms_used = create_algorithms_and_category_map(
        algorithms_data=results.algorithms,
        logger=job_logger,
    )

    detections = create_detections(
        detections=results.detections,
        algorithms_used=algorithms_used,
        logger=job_logger,
    )

    create_classifications(
        detections=detections,
        detection_responses=results.detections,
        algorithms_used=algorithms_used,
        logger=job_logger,
    )

    # Create a new occurrence for each detection (no tracking yet)
    # @TODO remove when we implement tracking!
    create_and_update_occurrences_for_detections(
        detections=detections,
        logger=job_logger,
    )

    # Update precalculated counts on source images and events
    # collect all source images for the detections
    for source_image in source_images:
        source_image.save()

    image_cropping_task = create_detection_images.delay(
        source_image_ids=[source_image.pk for source_image in source_images],
    )
    job_logger.info(f"Creating detection images in sub-task {image_cropping_task.id}")

    event_ids = [img.event_id for img in source_images]  # type: ignore
    update_calculated_fields_for_events(pks=event_ids)

    registered_algos = pipeline.algorithms.all()
    for algo in algorithms_used.values():
        # This is important for tracking what objects were processed by which algorithms
        # to avoid reprocessing, and for tracking provenance.
        if algo not in registered_algos:
            pipeline.algorithms.add(algo)
            job_logger.debug(f"Added algorithm {algo} to pipeline {pipeline}")

    if return_created:
        return []

    total_time = time.time() - start_time
    job_logger.info(f"Saved results from pipeline {pipeline} in {total_time:.2f} seconds")


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
    algorithms = models.ManyToManyField("ml.Algorithm", related_name="pipelines")
    stages: list[PipelineStage] = SchemaField(
        default=default_stages,
        help_text=(
            "The stages of the pipeline. This is mainly for display. "
            "The backend implementation of the pipeline may process data in any way."
        ),
    )
    projects = models.ManyToManyField("main.Project", related_name="pipelines", blank=True)
    endpoint_url = models.CharField(max_length=1024, null=True, blank=True)

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
