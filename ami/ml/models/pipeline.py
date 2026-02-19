from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models import ProcessingService, ProjectPipelineConfig

import collections
import dataclasses
import logging
import time
import typing
import uuid
from urllib.parse import urljoin

import requests
from django.db import models
from django.utils.text import slugify
from django.utils.timezone import now
from django_pydantic_field import SchemaField

from ami.base.models import BaseModel, BaseQuerySet
from ami.base.schemas import ConfigurableStage, default_stages
from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Occurrence,
    Project,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    TaxonRank,
    update_calculated_fields_for_events,
    update_occurrence_determination,
)
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models.algorithm import Algorithm, AlgorithmCategoryMap, AlgorithmTaskType
from ami.ml.schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    ClassificationResponse,
    DetectionRequest,
    DetectionResponse,
    PipelineRequest,
    PipelineRequestConfigParameters,
    PipelineResultsResponse,
    SourceImageRequest,
    SourceImageResponse,
)
from ami.ml.tasks import celery_app, create_detection_images
from ami.utils.requests import create_session, extract_error_message_from_response

logger = logging.getLogger(__name__)


def filter_processed_images(
    images: typing.Iterable[SourceImage],
    pipeline: Pipeline,
    task_logger: logging.Logger = logger,
) -> typing.Iterable[SourceImage]:
    """
    Return only images that need to be processed by a given pipeline.
    An image needs processing if:
    1. It has no detections from the pipeline's detection algorithm
    or
    2. It has detections but they don't have classifications from all the pipeline's classification algorithms
    """
    pipeline_algorithms = pipeline.algorithms.all()

    detection_type_keys = Algorithm.detection_task_types
    detection_algorithms = pipeline_algorithms.filter(task_type__in=detection_type_keys)
    if not detection_algorithms.exists():
        task_logger.warning(f"Pipeline {pipeline} has no detection algorithms saved. Will reprocess all images.")
    classification_algorithms = pipeline_algorithms.exclude(task_type__in=detection_type_keys)
    if not classification_algorithms.exists():
        task_logger.warning(f"Pipeline {pipeline} has no classification algorithms saved. Will reprocess all images.")

    for image in images:
        existing_detections = image.detections.filter(detection_algorithm__in=pipeline_algorithms)
        if not existing_detections.exists():
            task_logger.debug(f"Image {image} needs processing: has no existing detections from pipeline's detector")
            # If there are no existing detections from this pipeline, send the image
            yield image
        elif existing_detections.filter(classifications__isnull=True).exists():
            # Check if there are detections with no classifications
            task_logger.debug(
                f"Image {image} needs processing: has existing detections with no classifications "
                "from pipeline {pipeline}"
            )
            yield image
        else:
            # If there are existing detections with classifications,
            # Compare their classification algorithms to the current pipeline's algorithms
            pipeline_algorithm_ids = set(classification_algorithms.values_list("id", flat=True))
            detection_algorithm_ids = set(existing_detections.values_list("classifications__algorithm_id", flat=True))

            if not pipeline_algorithm_ids.issubset(detection_algorithm_ids):
                task_logger.debug(
                    f"Image {image} has existing detections that haven't been classified by the pipeline: {pipeline}:"
                    f" {detection_algorithm_ids} vs {pipeline_algorithm_ids}"
                    f"Since we do yet have a mechanism to reclassify detections, processing the image from scratch."
                )
                # log all algorithms that are in the pipeline but not in the detection
                missing_algos = pipeline_algorithm_ids - detection_algorithm_ids
                task_logger.debug(f"Image #{image.pk} needs classification by pipeline's algorithms: {missing_algos}")
                yield image
            else:
                # If all detections have been classified by the pipeline, skip the image
                task_logger.debug(
                    f"Image {image} has existing detections classified by the pipeline: {pipeline}, skipping!"
                )
                continue


def collect_images(
    collection: SourceImageCollection | None = None,
    source_images: list[SourceImage] | None = None,
    deployment: Deployment | None = None,
    job_id: int | None = None,
    pipeline: Pipeline | None = None,
    reprocess_all_images: bool = False,
) -> typing.Iterable[SourceImage]:
    """
    Collect images from a collection, a list of images or a deployment.
    """
    task_logger = logger
    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        task_logger = job.logger
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
    if pipeline and not reprocess_all_images:
        msg = f"Filtering images that have already been processed by pipeline {pipeline}"
        task_logger.info(msg)
        images = list(filter_processed_images(images, pipeline, task_logger=task_logger))
    else:
        msg = "NOT filtering images that have already been processed"
        task_logger.info(msg)

    msg = f"Found {len(images)} out of {total_images} images to process"
    task_logger.info(msg)

    return images


def process_images(
    pipeline: Pipeline,
    endpoint_url: str,
    images: typing.Iterable[SourceImage],
    job_id: int | None = None,
    project_id: int | None = None,
    reprocess_all_images: bool = False,
) -> PipelineResultsResponse:
    """
    Process images using ML pipeline API.
    """
    job = None
    task_logger = logger

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        task_logger = job.logger

    if project_id:
        project = Project.objects.get(pk=project_id)
    else:
        task_logger.warning(f"Pipeline {pipeline} is not associated with a project")
        project = None

    pipeline_config = pipeline.get_config(project_id=project_id)
    task_logger.info(f"Using pipeline config: {pipeline_config}")

    prefiltered_images = list(images)
    if reprocess_all_images:
        images = prefiltered_images
    else:
        images = list(filter_processed_images(images=prefiltered_images, pipeline=pipeline, task_logger=task_logger))

    if len(images) < len(prefiltered_images):
        # Log how many images were filtered out because they have already been processed
        task_logger.info(f"Ignoring {len(prefiltered_images) - len(images)} images that have already been processed")

    if not images:
        task_logger.info("No images to process")
        return PipelineResultsResponse(
            pipeline=pipeline.slug,
            source_images=[],
            detections=[],
            total_time=0,
        )
    task_logger.info(f"Sending {len(images)} images to Pipeline {pipeline}")
    urls = [source_image.public_url() for source_image in images if source_image.public_url()]

    source_image_requests: list[SourceImageRequest] = []
    detection_requests: list[DetectionRequest] = []

    reprocess_existing_detections = reprocess_all_images
    # Check if feature flag is enabled to reprocess existing detections
    if project and project.feature_flags.reprocess_existing_detections:
        # Check if the user wants to reprocess existing detections or ignore them
        if pipeline_config.get("reprocess_existing_detections", True):
            reprocess_existing_detections = True

    for source_image, url in zip(images, urls):
        if url:
            source_image_request = SourceImageRequest(
                id=str(source_image.pk),
                url=url,
            )
            source_image_requests.append(source_image_request)

            if reprocess_existing_detections:
                detection_requests += collect_detections(source_image, source_image_request)

    if reprocess_existing_detections:
        task_logger.info(f"Found {len(detection_requests)} existing detections to reprocess.")
    else:
        task_logger.info("Reprocessing of existing detections is disabled, sending images without detections.")

    request_data = PipelineRequest(
        pipeline=pipeline.slug,
        source_images=source_image_requests,
        config=pipeline_config,
        detections=detection_requests,
    )
    task_logger.debug(f"Pipeline request data: {request_data}")

    session = create_session()
    resp = session.post(endpoint_url, json=request_data.dict())
    if not resp.ok:
        summary = request_data.summary()
        error_msg = extract_error_message_from_response(resp)
        msg = f"Failed to process {summary}: {error_msg}"

        if job:
            job.logger.error(msg)
        else:
            logger.error(msg)
            raise requests.HTTPError(msg)

        results = PipelineResultsResponse(
            pipeline=pipeline.slug,
            total_time=0,
            source_images=[
                SourceImageResponse(id=source_image_request.id, url=source_image_request.url)
                for source_image_request in source_image_requests
            ],
            detections=[],
            errors=msg,
        )
        return results

    results = resp.json()
    results = PipelineResultsResponse(**results)
    if job:
        job.logger.debug(f"Results: {results}")
        detections = results.detections
        classifications = [classification for detection in detections for classification in detection.classifications]
        job.logger.info(
            f"Pipeline results returned {len(results.source_images)} images, {len(detections)} detections, "
            f"{len(classifications)} classifications"
        )

    return results


def collect_detections(
    source_image: SourceImage,
    source_image_request: SourceImageRequest,
) -> list[DetectionRequest]:
    """
    Collect existing detections for a source image and send them with pipeline request.
    """
    detection_requests: list[DetectionRequest] = []
    # Re-process all existing detections if they exist
    for detection in source_image.detections.all():
        bbox = detection.get_bbox()
        if bbox and detection.detection_algorithm:
            detection_requests.append(
                DetectionRequest(
                    source_image=source_image_request,
                    bbox=bbox,
                    crop_image_url=detection.url(),
                    algorithm=AlgorithmReference(
                        name=detection.detection_algorithm.name,
                        key=detection.detection_algorithm.key,
                    ),
                )
            )

    return detection_requests


def get_or_create_algorithm_and_category_map(
    algorithm_config: AlgorithmConfigResponse,
    logger: logging.Logger = logger,
) -> Algorithm:
    """
    Create algorithms and category maps from a ProcessingServiceInfoResponse or a PipelineConfigResponse.

    :param algorithm_configs: A dictionary of algorithms from the processing services' "/info" endpoint
    :param logger: A logger instance from the parent function

    :return: A dictionary of algorithms registered in the pipeline, keyed by the algorithm key

    @TODO this should be called when registering a pipeline, not when saving results.
    But currently we don't have a way to register pipelines.
    """
    algo, _created = Algorithm.objects.get_or_create(
        key=algorithm_config.key,
        version=algorithm_config.version,
        defaults={
            "name": algorithm_config.name,
            "task_type": algorithm_config.task_type,
            "version_name": algorithm_config.version_name,
            "uri": algorithm_config.uri,
            "category_map": None,
        },
    )
    if _created:
        logger.info(f"Registered new algorithm {algo}")
    else:
        logger.info(f"Using existing algorithm {algo}")

    algo_fields_updated = []
    new_category_map = None
    category_map_data = algorithm_config.category_map

    if not algo.has_valid_category_map():
        if category_map_data:
            # New algorithms will not have a category map yet, and older ones may not either
            # The category map data should be in the algorithm config from the /info endpoint
            new_category_map = AlgorithmCategoryMap.objects.create(
                version=category_map_data.version,
                data=category_map_data.data,
                labels=category_map_data.labels,
                description=category_map_data.description,
                uri=category_map_data.uri,
            )
            algo.category_map = new_category_map
            algo_fields_updated.append("category_map")
            logger.info(f"Registered new category map {new_category_map} for algorithm {algo}")
        else:
            if algorithm_config.task_type in Algorithm.classification_task_types:
                msg = (
                    f"No valid category map found for algorithm '{algorithm_config.key}' with "
                    f"task type '{algorithm_config.task_type}' or in the pipeline /info response. "
                    "Update the processing service to include a category map for all classification algorithms "
                    "then re-register the pipelines."
                )
                raise PipelineNotConfigured(msg)
            else:
                logger.debug(f"No category map found, but not required for task type {algorithm_config.task_type}")

    # Update fields that may have changed in the processing service, with a warning
    # These are fields that we have added to the API since the algorithm was first created
    fields_to_update = {
        "task_type": algorithm_config.task_type,
        "uri": algorithm_config.uri,
    }
    for field in fields_to_update:
        new_value = fields_to_update[field]
        if getattr(algo, field) != new_value:
            logger.warning(f"Field '{field}' changed for algorithm {algo} from {getattr(algo, field)} to {new_value}")
            setattr(algo, field, new_value)
            algo_fields_updated.append(field)

    if algo_fields_updated:
        algo.save(update_fields=algo_fields_updated)

    return algo


def get_or_create_detection(
    source_image: SourceImage,
    detection_resp: DetectionResponse,
    algorithms_known: dict[str, Algorithm],
    save: bool = True,
    logger: logging.Logger = logger,
) -> tuple[Detection, bool]:
    """
    Create a Detection object from a DetectionResponse, or update an existing one.

    :param detection_resp: A DetectionResponse object
    :param algorithms_known: A dictionary of algorithms registered in the pipeline, keyed by the algorithm key
    :param created_objects: A list to store created objects

    :return: A tuple of the Detection object and a boolean indicating whether it was created
    """
    if detection_resp.bbox is not None:
        serialized_bbox = list(detection_resp.bbox.dict().values())
    else:
        serialized_bbox = None
    detection_repr = f"Detection {detection_resp.source_image_id} {serialized_bbox}"

    assert str(detection_resp.source_image_id) == str(
        source_image.pk
    ), f"Detection belongs to a different source image: {detection_repr}"

    existing_detection = Detection.objects.filter(
        source_image=source_image,
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
        assert detection_resp.algorithm, f"No detection algorithm was specified for detection {detection_repr}"
        try:
            detection_algo = algorithms_known[detection_resp.algorithm.key]
        except KeyError:
            raise PipelineNotConfigured(
                f"Detection algorithm {detection_resp.algorithm.key} is not a known algorithm. "
                "The processing service must declare it in the /info endpoint. "
                f"Known algorithms: {list(algorithms_known.keys())}"
            )

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
    algorithms_known: dict[str, Algorithm],
    logger: logging.Logger = logger,
) -> list[Detection]:
    """
    Efficiently create multiple Detection objects from a list of DetectionResponse objects, grouped by source image.
    Using bulk create.

    :param detections: A list of DetectionResponse objects
    :param algorithms_known: A dictionary of algorithms registered in the pipeline, keyed by the algorithm key
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
            algorithms_known=algorithms_known,
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
    taxa_list, created = TaxaList.objects.get_or_create(
        name=f"Taxa returned by {algorithm.name}",
    )
    if created:
        logger.info(f"Created new taxa list {taxa_list}")
    else:
        logger.debug(f"Using existing taxa list {taxa_list}")

    # Get top label from classification scores
    assert algorithm.category_map, f"No category map found for algorithm {algorithm}"
    label_data: dict = algorithm.category_map.data[classification_resp.scores.index(max(classification_resp.scores))]
    returned_taxon_name = classification_resp.classification
    # @TODO standardize the Taxon search / lookup. See similar query in ml.models.algorithm.AlgorithmCategoryMap
    taxon = Taxon.objects.filter(
        models.Q(name=returned_taxon_name) | models.Q(search_names__overlap=[returned_taxon_name]),
        active=True,
    ).first()
    if not taxon:
        taxon = Taxon.objects.create(
            name=returned_taxon_name,
            rank=label_data.get("taxon_rank", TaxonRank.UNKNOWN),
        )
        logger.info(f"Registered new taxon {taxon}")

    taxa_list.taxa.add(taxon)
    return taxon


def create_classification(
    detection: Detection,
    classification_resp: ClassificationResponse,
    algorithms_known: dict[str, Algorithm],
    save: bool = True,
    logger: logging.Logger = logger,
) -> tuple[Classification, bool]:
    """
    Create a Classification object from a ClassificationResponse, or update an existing one.

    :param detection: A Detection object
    :param classification: A ClassificationResponse object
    :param algorithms_known: A dictionary of algorithms registered in the pipeline, keyed by the algorithm key
    :param created_objects: A list to store created objects

    :return: A tuple of the Classification object and a boolean indicating whether it was created
    """
    assert (
        classification_resp.algorithm
    ), f"No classification algorithm was specified for classification {classification_resp}"
    logger.debug(f"Processing classification {classification_resp}")

    try:
        classification_algo = algorithms_known[classification_resp.algorithm.key]
    except KeyError:
        raise PipelineNotConfigured(
            f"Classification algorithm {classification_resp.algorithm.key} is not a known algorithm. "
            "The processing service must declare it in the /info endpoint. "
            f"Known algorithms: {list(algorithms_known.keys())}"
        )

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
        # @TODO remove this after all existing classifications have been updated (added 2024-12-20)
        NEW_FIELDS = ["logits", "scores", "terminal", "category_map"]
        logger.debug(
            "Duplicate classification found: "
            f"{existing_classification.taxon} from {existing_classification.algorithm}, "
            f"not creating a new one, but updating new fields if they are None ({NEW_FIELDS})"
        )
        fields_to_update = []
        for field in NEW_FIELDS:
            # update new fields if they are None
            if getattr(existing_classification, field) is None:
                fields_to_update.append(field)
        if fields_to_update:
            logger.info(f"Updating fields {fields_to_update} for existing classification {existing_classification}")
            for field in fields_to_update:
                if field == "category_map":
                    # Use the foreign key from the classification algorithm
                    setattr(existing_classification, field, classification_algo.category_map)
                else:
                    # Get the value from the classification response
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
            category_map=classification_algo.category_map,
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
    algorithms_known: dict[str, Algorithm],
    logger: logging.Logger = logger,
    save: bool = True,
) -> list[Classification]:
    """
    Efficiently create multiple Classification objects from a list of ClassificationResponse objects,
    grouped by detection.

    :param detection: A Detection object
    :param classifications: A list of ClassificationResponse objects
    :param algorithms_known: A dictionary of algorithms registered in the pipeline, keyed by the algorithm key

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
                algorithms_known=algorithms_known,
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
        f"classifications for {len(detections)} detections."
    )

    return existing_classifications + new_classifications


def create_and_update_occurrences_for_detections(
    detections: list[Detection],
    logger: logging.Logger = logger,
):
    """
    Create an Occurrence object for each Detection, and update the occurrence determination.

    Select the best terminal classification for the occurrence determination.

    :param detection: A Detection object
    :param classifications: A list of Classification objects

    :return: The Occurrence object
    """

    # Group detections by source image id so we don't create duplicate occurrences
    detections_by_source_image = collections.defaultdict(list)
    for detection in detections:
        detections_by_source_image[detection.source_image_id].append(detection)

    for source_image_id, detections in detections_by_source_image.items():
        logger.info(f"Determining occurrences for {len(detections)} detections for source image {source_image_id}")

        occurrences_to_create = []
        detections_to_update = []

        for detection in detections:
            if not detection.occurrence:
                occurrence = Occurrence(
                    event=detection.source_image.event,
                    deployment=detection.source_image.deployment,
                    project=detection.source_image.project,
                )
                occurrences_to_create.append(occurrence)
                logger.debug(f"Created new occurrence {occurrence} for detection {detection}")
                detection.occurrence = occurrence  # type: ignore
                detections_to_update.append(detection)

        occurrences = Occurrence.objects.bulk_create(occurrences_to_create)
        logger.info(f"Created {len(occurrences)} new occurrences")
        Detection.objects.bulk_update(detections_to_update, ["occurrence"])
        logger.info(f"Updated {len(detections_to_update)} detections with occurrences")

        occurrences_to_update = []
        occurrences_to_leave = []
        for detection in detections:
            assert detection.occurrence, f"No occurrence found for detection {detection}"
            needs_update = update_occurrence_determination(
                detection.occurrence,
                current_determination=detection.occurrence.determination,
                save=False,
            )
            if needs_update:
                occurrences_to_update.append(detection.occurrence)
            else:
                occurrences_to_leave.append(detection.occurrence)

        Occurrence.objects.bulk_update(occurrences_to_update, ["determination", "determination_score"])
        logger.info(
            f"Updated the determination of {len(occurrences_to_update)} occurrences, "
            f"left {len(occurrences_to_leave)} unchanged"
        )

        SourceImage.objects.get(pk=source_image_id).save()


@dataclasses.dataclass
class PipelineSaveResults:
    pipeline: Pipeline
    source_images: list[SourceImage]
    detections: list[Detection]
    classifications: list[Classification]
    algorithms: dict[str, Algorithm]
    total_time: float


def create_null_detections_for_undetected_images(
    results: PipelineResultsResponse,
    algorithms_known: dict[str, Algorithm],
    logger: logging.Logger = logger,
) -> list[DetectionResponse]:
    """
    Create null DetectionResponse objects (empty bbox) for images that have no detections.

    :param results: The PipelineResultsResponse from the processing service
    :param algorithms_known: Dictionary of algorithms keyed by algorithm key

    :return: List of DetectionResponse objects with null bbox
    """
    source_images_with_detections = {int(detection.source_image_id) for detection in results.detections}
    null_detections_to_add = []

    for source_img in results.source_images:
        if int(source_img.id) not in source_images_with_detections:
            detector_algorithm_reference = None
            for known_algorithm in algorithms_known.values():
                if known_algorithm.task_type == AlgorithmTaskType.DETECTION:
                    detector_algorithm_reference = AlgorithmReference(
                        name=known_algorithm.name, key=known_algorithm.key
                    )

            if detector_algorithm_reference is None:
                logger.error(
                    f"Could not identify the detector algorithm. "
                    f"A null detection was not created for Source Image {source_img.id}"
                )
                continue

            null_detections_to_add.append(
                DetectionResponse(
                    source_image_id=source_img.id,
                    bbox=None,
                    algorithm=detector_algorithm_reference,
                    timestamp=now(),
                )
            )

    return null_detections_to_add


@celery_app.task(soft_time_limit=60 * 4, time_limit=60 * 5)
def save_results(
    results: PipelineResultsResponse | None = None,
    results_json: str | None = None,
    job_id: int | None = None,
    return_created=False,
) -> PipelineSaveResults | None:
    """
    Save results from ML pipeline API.

    @TODO Continue improving bulk create. Group everything / all loops by source image.
    """
    job = None

    if results_json:
        results = PipelineResultsResponse.parse_raw(results_json)
    assert results, "No results data passed to save_results task"

    pipeline, _created = Pipeline.objects.get_or_create(slug=results.pipeline, defaults={"name": results.pipeline})
    if _created:
        logger.warning(f"Pipeline choice returned by the Processing Service was not recognized! {pipeline}")

    job_logger = logger
    start_time = time.time()

    if job_id:
        from ami.jobs.models import Job

        job = Job.objects.get(pk=job_id)
        job_logger = job.logger

    if results_json:
        results = PipelineResultsResponse.parse_raw(results_json)
    assert results, "No results data passed to save_results task"
    job_logger.info(f"Saving results from pipeline {results.pipeline}")

    results = PipelineResultsResponse.parse_obj(results.dict())
    assert results, "No results from pipeline to save"
    source_images = SourceImage.objects.filter(pk__in=[int(img.id) for img in results.source_images]).distinct()

    pipeline, _created = Pipeline.objects.get_or_create(slug=results.pipeline, defaults={"name": results.pipeline})
    if _created:
        job_logger.warning(
            f"The pipeline returned by the ML backend was not recognized, created a placeholder: {pipeline}"
        )

    algorithms_known: dict[str, Algorithm] = {algo.key: algo for algo in pipeline.algorithms.all()}
    job_logger.info(f"Algorithms registered for pipeline: \n{', '.join(algorithms_known.keys())}")

    if results.algorithms:
        logger.warning(
            "Algorithms were returned by the processing service in the results, these will be ignored and "
            "they should be removed to increase performance. "
            "Algorithms and category maps must be registered before processing, using /info endpoint."
        )

    # Ensure all images have detections
    # if not, add a NULL detection (empty bbox) to the results
    null_detections = create_null_detections_for_undetected_images(
        results=results,
        algorithms_known=algorithms_known,
        logger=job_logger,
    )
    results.detections = results.detections + null_detections

    detections = create_detections(
        detections=results.detections,
        algorithms_known=algorithms_known,
        logger=job_logger,
    )

    classifications = create_classifications(
        detections=detections,
        detection_responses=results.detections,
        algorithms_known=algorithms_known,
        logger=job_logger,
    )

    # Create a new occurrence for each detection (no tracking yet)
    # @TODO remove when we implement tracking!
    create_and_update_occurrences_for_detections(
        detections=detections,
        logger=job_logger,
    )

    # Update precalculated counts on source images and events
    source_images = list(source_images)
    logger.info(f"Updating calculated fields for {len(source_images)} source images")
    for source_image in source_images:
        source_image.save()

    image_cropping_task = create_detection_images.delay(
        source_image_ids=[source_image.pk for source_image in source_images],
    )
    job_logger.info(f"Creating detection images in sub-task {image_cropping_task.id}")

    event_ids = [img.event_id for img in source_images]  # type: ignore
    update_calculated_fields_for_events(pks=event_ids)

    total_time = time.time() - start_time
    job_logger.info(f"Saved results from pipeline {pipeline} in {total_time:.2f} seconds")

    if return_created:
        """
        By default, return None because celery tasks need special handling to return objects.
        """
        # Collect only algorithms that were actually used in detections or classifications
        detection_algos = {det.detection_algorithm for det in detections if det.detection_algorithm}
        classification_algos = {clss.algorithm for clss in classifications if clss.algorithm}
        algorithms_used: dict[str, Algorithm] = {algo.key: algo for algo in detection_algos | classification_algos}

        return PipelineSaveResults(
            pipeline=pipeline,
            source_images=source_images,
            detections=detections,
            classifications=classifications,
            algorithms=algorithms_used,
            total_time=total_time,
        )


class PipelineStage(ConfigurableStage):
    """A configurable stage of a pipeline."""


class PipelineQuerySet(BaseQuerySet):
    """Custom QuerySet for Pipeline model."""

    def enabled(self, project: Project) -> PipelineQuerySet:
        """
        Return pipelines that are enabled for a given project.

        # @TODO how can this automatically filter based on the pipeline's projects
        # or the current query without having to specify the project? (e.g. with OuterRef?)
        """
        return self.filter(
            projects=project,
            project_pipeline_configs__enabled=True,
            project_pipeline_configs__project=project,
            processing_services__projects=project,
        ).distinct()

    def online(self, project: Project) -> PipelineQuerySet:
        """
        Return pipelines that are available at least one online processing service.
        """
        return self.filter(
            processing_services__projects=project,
            processing_services__last_checked_live=True,
        ).distinct()


class PipelineManager(models.Manager):
    """Custom Manager for Pipeline model."""

    def get_queryset(self) -> PipelineQuerySet:
        return PipelineQuerySet(self.model, using=self._db)


@typing.final
class Pipeline(BaseModel):
    """A pipeline of algorithms"""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    version = models.IntegerField(default=1)
    version_name = models.CharField(max_length=255, blank=True)
    # @TODO add support for ordered algorithms in the pipeline, for know the order is only in the stages config
    algorithms = models.ManyToManyField("ml.Algorithm", related_name="pipelines")
    stages: list[PipelineStage] = SchemaField(
        default=default_stages,
        help_text=(
            "The stages of the pipeline. This is mainly for display. "
            "The backend implementation of the pipeline may process data in any way."
        ),
    )
    projects = models.ManyToManyField(
        "main.Project", related_name="pipelines", blank=True, through="ml.ProjectPipelineConfig"
    )
    default_config: PipelineRequestConfigParameters = SchemaField(
        schema=PipelineRequestConfigParameters,
        default=dict,
        blank=True,
        help_text=(
            "The default configuration for the pipeline. "
            "Used by both the job sending images to the pipeline "
            "and the processing service."
        ),
    )

    objects = PipelineManager()

    processing_services: models.QuerySet[ProcessingService]
    project_pipeline_configs: models.QuerySet[ProjectPipelineConfig]
    jobs: models.QuerySet[Job]

    class Meta:
        ordering = ["name", "version"]

        unique_together = [
            ["name", "version"],
        ]

    def __str__(self):
        return f'#{self.pk} "{self.name}" ({self.slug}) v{self.version}'

    def get_config(self, project_id: int | None = None) -> PipelineRequestConfigParameters:
        """
        Get the configuration for the pipeline request.

        This will be the same as pipeline.default_config, but if a project ID is provided,
        the project's pipeline config will be used to override the default config.
        """
        config = self.default_config
        if project_id:
            try:
                project_pipeline_config = self.project_pipeline_configs.get(project_id=project_id)
                if project_pipeline_config.config:
                    config.update(project_pipeline_config.config)
                logger.debug(
                    f"Using ProjectPipelineConfig for Pipeline {self} and Project #{project_id}:" f"config: {config}"
                )
            except self.project_pipeline_configs.model.DoesNotExist as e:
                logger.warning(f"No project-pipeline config for Pipeline {self} " f"and Project #{project_id}: {e}")
        return config

    def collect_images(
        self,
        collection: SourceImageCollection | None = None,
        source_images: list[SourceImage] | None = None,
        deployment: Deployment | None = None,
        job_id: int | None = None,
        reprocess_all_images: bool = False,
    ) -> typing.Iterable[SourceImage]:
        return collect_images(
            collection=collection,
            source_images=source_images,
            deployment=deployment,
            job_id=job_id,
            pipeline=self,
            reprocess_all_images=reprocess_all_images,
        )

    def choose_processing_service_for_pipeline(
        self, job_id: int | None, pipeline_name: str, project_id: int
    ) -> ProcessingService:
        # @TODO use the cached `last_checked_latency` and a max age to avoid checking every time

        job = None
        task_logger = logger
        if job_id:
            from ami.jobs.models import Job

            job = Job.objects.get(pk=job_id)
            task_logger = job.logger

        # get all processing services that are associated with the provided pipeline project
        processing_services = self.processing_services.filter(projects=project_id)
        task_logger.info(
            f"Searching processing services:"
            f"{[processing_service.name for processing_service in processing_services]}"
        )

        # check the status of all processing services and pick the one with the lowest latency
        lowest_latency = float("inf")
        processing_services_online = False

        for processing_service in processing_services:
            if processing_service.last_checked_live:
                processing_services_online = True
                if (
                    processing_service.last_checked_latency
                    and processing_service.last_checked_latency < lowest_latency
                ):
                    lowest_latency = processing_service.last_checked_latency
                    # pick the processing service that has lowest latency
                    processing_service_lowest_latency = processing_service

        # if all offline then throw error
        if not processing_services_online:
            msg = f'No processing services are online for the pipeline "{pipeline_name}".'
            task_logger.error(msg)

            raise Exception(msg)
        else:
            task_logger.info(
                f"Using processing service with latency {round(lowest_latency, 4)}: "
                f"{processing_service_lowest_latency}"
            )

            return processing_service_lowest_latency

    def process_images(
        self,
        images: typing.Iterable[SourceImage],
        project_id: int,
        job_id: int | None = None,
        reprocess_all_images: bool = False,
    ) -> PipelineResultsResponse:
        processing_service = self.choose_processing_service_for_pipeline(job_id, self.name, project_id)

        if not processing_service.endpoint_url:
            raise PipelineNotConfigured(
                f"No endpoint URL configured for this pipeline's processing service ({processing_service})"
            )

        return process_images(
            endpoint_url=urljoin(processing_service.endpoint_url, "/process"),
            pipeline=self,
            images=images,
            job_id=job_id,
            project_id=project_id,
            reprocess_all_images=reprocess_all_images,
        )

    def save_results(self, results: PipelineResultsResponse, job_id: int | None = None):
        return save_results(results=results, job_id=job_id)

    def save_results_async(self, results: PipelineResultsResponse, job_id: int | None = None):
        # Returns an AsyncResult
        results_json = results.json()
        return save_results.delay(results_json=results_json, job_id=job_id)

    def save(self, *args, **kwargs):
        if not self.slug:
            # @TODO find a better way to generate unique identifiers
            # consider hashing the pipeline config or using a UUID -- but both sides need to agree on the same UUID.
            unique_suffix = str(uuid.uuid4())[:8]
            self.slug = f"{slugify(self.name)}-v{self.version}-{unique_suffix}"
        return super().save(*args, **kwargs)
