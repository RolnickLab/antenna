import datetime
import logging
import math
import random

from . import algorithms
from .schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    Detection,
    DetectionResponse,
    PipelineConfigResponse,
    SourceImage,
)
from .utils import get_image

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def make_constant_detection(source_images: list[SourceImage]) -> list[Detection]:
    """
    For each source image, produce a fixed bounding box size and position relative to image size. No classification.
    """
    detector_responses: list[Detection] = []
    for source_image in source_images:
        source_image.open(raise_exception=True)

        if source_image.width and source_image.height and source_image._pil:
            start_time = datetime.datetime.now()
            # For each source image, produce a fixed bounding box size and position relative to image size
            box_width, box_height = source_image.width // 4, source_image.height // 4
            start_x, start_y = source_image.width // 8, source_image.height // 8
            bbox = BoundingBox(
                x1=start_x,
                y1=start_y,
                x2=start_x + box_width,
                y2=start_y + box_height,
            )
            cropped_image_pil = source_image._pil.crop((bbox.x1, bbox.y1, bbox.x2, bbox.y2))
            end_time = datetime.datetime.now()
            elapsed_time = (end_time - start_time).total_seconds()

            detector_responses.append(
                Detection(
                    id=f"{source_image.id}-crop-{bbox.x1}-{bbox.y1}-{bbox.x2}-{bbox.y2}",
                    url=source_image.url,
                    width=cropped_image_pil.width,
                    height=cropped_image_pil.height,
                    timestamp=datetime.datetime.now(),
                    source_image=source_image,
                    bbox=bbox,
                    inference_time=elapsed_time,
                    algorithm=AlgorithmReference(
                        name=algorithms.CONSTANT_DETECTOR.name,
                        key=algorithms.CONSTANT_DETECTOR.key,
                    ),
                )
            )

    return detector_responses


def make_random_prediction(
    algorithm: AlgorithmConfigResponse,
    terminal: bool = True,
    max_labels: int = 2,
) -> ClassificationResponse:
    """
    Helper function to generate a random classification response.
    """
    assert algorithm.category_map is not None
    category_labels = algorithm.category_map.labels
    logits = [random.random() for _ in category_labels]
    softmax = [math.exp(logit) / sum([math.exp(logit) for logit in logits]) for logit in logits]
    top_class = category_labels[softmax.index(max(softmax))]
    return ClassificationResponse(
        classification=top_class,
        labels=category_labels if len(category_labels) <= max_labels else None,
        scores=softmax,
        logits=logits,
        timestamp=datetime.datetime.now(),
        algorithm=AlgorithmReference(name=algorithm.name, key=algorithm.key),
        terminal=terminal,
    )


def make_classifications(detections: list[Detection], type: str) -> list[DetectionResponse]:
    """
    Given a list of detections, return a list of detection responses containing classifications.
    The classification type can be either "constant" or "random".
    """
    if type == "constant":
        assert algorithms.CONSTANT_CLASSIFIER.category_map is not None
        labels = algorithms.CONSTANT_CLASSIFIER.category_map.labels
        classifications = [
            ClassificationResponse(
                classification=labels[0],
                labels=labels,
                scores=[0.9],
                timestamp=datetime.datetime.now(),
                algorithm=AlgorithmReference(
                    name=algorithms.CONSTANT_CLASSIFIER.name, key=algorithms.CONSTANT_CLASSIFIER.key
                ),
            )
        ]
    elif type == "random":
        classifications = [
            make_random_prediction(
                algorithm=algorithms.RANDOM_BINARY_CLASSIFIER,
                terminal=False,
            ),
            make_random_prediction(
                algorithm=algorithms.RANDOM_SPECIES_CLASSIFIER,
                terminal=True,
            ),
        ]
    else:
        raise ValueError(f"Classification type must be constant or random, not {type}.")

    return [
        DetectionResponse(
            source_image_id=detection.source_image.id,
            bbox=detection.bbox,
            timestamp=datetime.datetime.now(),
            inference_time=0.01,  # filler value of constant time
            algorithm=detection.algorithm,
            classifications=classifications,
        )
        for detection in detections
    ]


class Pipeline:
    config = PipelineConfigResponse(
        name="Base Pipeline",
        slug="base",
        description="A base class for all pipelines.",
        version=1,
        algorithms=[],
    )

    def __init__(
        self,
        source_images: list[SourceImage],
        existing_detections: list[Detection],
    ):
        self.source_images = source_images
        self.existing_detections = existing_detections

    def run(self) -> list[DetectionResponse]:
        raise NotImplementedError("Subclasses must implement the run method")

    def _process_existing_detections(self) -> list[Detection]:
        """
        Helper function for processing existing detections.
        Opens the source and cropped images, and crops the source image if the cropped image URL is not valid.
        """
        processed_detections = self.existing_detections.copy()

        for detection in processed_detections:
            logger.info(f"Processing existing detection: {detection.id}")
            detection.source_image.open(raise_exception=True)
            assert detection.source_image._pil is not None, "Source image must be opened before cropping."

            try:
                # @TODO: Is this necessary? Should we always crop the image ourselves?
                # The cropped image URL is typically a local file path.
                # e.g. /media/detections/1/2018-06-15/session_2018-06-15_capture_20180615220800_detection_54.jpg
                logger.info("Opening cropped image from the cropped image URL...")
                detection._pil = get_image(
                    url=detection.url,
                    raise_exception=True,
                )
            except Exception as e:
                logger.info(f"Failed to open cropped image from the URL: {detection.url}. Error: {e}")
                logger.info("Falling back to cropping the source image...")
                cropped_image_pil = detection.source_image._pil.crop(
                    (
                        min(detection.bbox.x1, detection.bbox.x2),
                        min(detection.bbox.y1, detection.bbox.y2),
                        max(detection.bbox.x1, detection.bbox.x2),
                        max(detection.bbox.y1, detection.bbox.y2),
                    )
                )
                detection._pil = cropped_image_pil
            logger.info(f"Successfully processed existing detection: {detection.id}")
        return processed_detections


class ConstantPipeline(Pipeline):
    """
    A pipeline that always returns a detection with the same bounding box
    and a fixed classification.
    """

    def run(self) -> list[DetectionResponse]:
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections: list[Detection] = self._process_existing_detections()
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections: list[Detection] = make_constant_detection(self.source_images)

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[DetectionResponse] = make_classifications(detections, "constant")

        return detections_with_classifications

    config = PipelineConfigResponse(
        name="Constant Pipeline",
        slug="constant",
        description="A pipeline that always returns a detection in the same position with a fixed classification.",
        version=1,
        algorithms=[
            algorithms.CONSTANT_DETECTOR,
            algorithms.CONSTANT_CLASSIFIER,
        ],
    )


class ConstantDetectionRandomSpeciesPipeline(Pipeline):
    """
    A pipeline that always returns a detection with the same bounding box
    but with a random species classification.
    """

    def run(self) -> list[DetectionResponse]:
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections: list[Detection] = self._process_existing_detections()
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections: list[Detection] = make_constant_detection(self.source_images)

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[DetectionResponse] = make_classifications(detections, "random")

        return detections_with_classifications

    config = PipelineConfigResponse(
        name="Constant Detection Random Species Pipeline",
        slug="constant-detection-random-species",
        description="A pipeline that always returns a detection in the same position with a random classification.",
        version=1,
        algorithms=[
            algorithms.CONSTANT_DETECTOR,
            algorithms.RANDOM_BINARY_CLASSIFIER,
            algorithms.RANDOM_SPECIES_CLASSIFIER,
        ],
    )
