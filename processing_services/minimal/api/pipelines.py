import datetime
import logging
import math
import random

from . import algorithms, vectors
from .schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    Detection,
    DetectionResponse,
    PipelineConfigResponse,
    PipelineRequestConfigParameters,
    SourceImage,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def make_constant_detection(source_images: list[SourceImage]) -> list[Detection]:
    """
    For each source image, produce a fixed bounding box size and position relative to image size. No classification.
    """
    detector_responses: list[Detection] = []
    for source_image in source_images:
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
        else:
            raise ValueError(f"Source image {source_image.id} could not be opened or does not have a valid PIL image.")

    return detector_responses


def make_random_detection(source_images: list[SourceImage]) -> list[Detection]:
    """
    For each source image, produce a random bounding box size and position relative to image size. No classification.
    """
    detector_responses: list[Detection] = []
    for source_image in source_images:
        if source_image.width and source_image.height and source_image._pil:
            start_time = datetime.datetime.now()
            # Produce a random bounding box size and position relative to image size
            min_box_size = min(source_image.width, source_image.height) // 8
            max_box_width = source_image.width // 2
            max_box_height = source_image.height // 2
            box_width = random.randint(min_box_size, max_box_width)
            box_height = random.randint(min_box_size, max_box_height)
            start_x = random.randint(0, source_image.width - box_width)
            start_y = random.randint(0, source_image.height - box_height)
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
                        name=algorithms.RANDOM_DETECTOR.name,
                        key=algorithms.RANDOM_DETECTOR.key,
                    ),
                )
            )
        else:
            raise ValueError(f"Source image {source_image.id} could not be opened or does not have a valid PIL image.")
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
    # The classifier whose own features are returned when features_for_all_detections is set.
    terminal_classifier: AlgorithmConfigResponse | None = None
    # The feature extractor this pipeline offers. It must also be listed in config.algorithms.
    feature_extractor: AlgorithmConfigResponse | None = None

    def __init__(
        self,
        source_images: list[SourceImage],
        existing_detections: list[Detection],
        request_config: PipelineRequestConfigParameters | None = None,
        detections_sent: bool = False,
    ):
        self.source_images = source_images
        self.existing_detections = existing_detections
        # True when the request carried detections, even if every one was skipped as empty.
        self.detections_sent = detections_sent
        self.request_config = request_config or PipelineRequestConfigParameters()
        self.extractor = self.resolve_extractor()

    def resolve_extractor(self) -> AlgorithmConfigResponse | None:
        """The extractor to run for this request, following the AMI Data Companion's rules.

        None runs the pipeline's own extractor, an empty string runs none, and any key other
        than the one the pipeline offers is an error.
        """
        requested = self.request_config.embedding_extractor
        if requested == "":
            return None
        if requested is None or (self.feature_extractor and requested == self.feature_extractor.key):
            return self.feature_extractor
        raise ValueError(
            f'Pipeline "{self.config.slug}" does not offer the feature extractor "{requested}". '
            f"Offered: {[self.feature_extractor.key] if self.feature_extractor else []}"
        )

    def run(self) -> list[DetectionResponse]:
        raise NotImplementedError("Subclasses must implement the run method")

    def finish(self, detections: list[DetectionResponse]) -> list[DetectionResponse]:
        """Apply the request config to the pipeline's output: drop logits, attach vectors."""
        for detection in detections:
            if not self.request_config.include_logits:
                for classification in detection.classifications:
                    classification.logits = None
            embedding_sources = []
            if self.request_config.features_for_all_detections and self.terminal_classifier:
                embedding_sources.append((self.terminal_classifier, vectors.CLASSIFIER_VECTOR_LENGTH))
            if self.extractor:
                embedding_sources.append((self.extractor, vectors.EXTRACTOR_VECTOR_LENGTH))
            for algorithm, length in embedding_sources:
                reference = AlgorithmReference(name=algorithm.name, key=algorithm.key)
                detection.embeddings = (detection.embeddings or []) + [
                    vectors.embedding_for(reference, detection.source_image_id, detection.bbox, length)
                ]
        return detections


class ConstantPipeline(Pipeline):
    """
    A pipeline that always returns a detection with the same bounding box
    and a fixed classification.
    """

    def run(self) -> list[DetectionResponse]:
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections: list[Detection] = self.existing_detections
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections: list[Detection] = make_constant_detection(self.source_images)

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[DetectionResponse] = make_classifications(detections, "constant")

        return self.finish(detections_with_classifications)

    terminal_classifier = algorithms.CONSTANT_CLASSIFIER

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


class RandomDetectionRandomSpeciesPipeline(Pipeline):
    """
    A pipeline that always returns a detection with a random bounding box size/position
    and a random species classification.
    """

    def run(self) -> list[DetectionResponse]:
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections: list[Detection] = self.existing_detections
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections: list[Detection] = make_random_detection(self.source_images)

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[DetectionResponse] = make_classifications(detections, "random")

        return self.finish(detections_with_classifications)

    terminal_classifier = algorithms.RANDOM_SPECIES_CLASSIFIER

    config = PipelineConfigResponse(
        name="Random Detection Random Species Pipeline",
        slug="random-detection-random-species",
        description="A pipeline that returns a random bbox with a random classification.",
        version=1,
        algorithms=[
            algorithms.RANDOM_DETECTOR,
            algorithms.RANDOM_BINARY_CLASSIFIER,
            algorithms.RANDOM_SPECIES_CLASSIFIER,
        ],
    )


class ConstantWithFeatureExtractorPipeline(ConstantPipeline):
    """The constant pipeline plus a feature extractor that adds a vector to every detection.

    Stands in for an AMI Data Companion deployment with an embedding extractor configured.
    """

    feature_extractor = algorithms.CONSTANT_FEATURE_EXTRACTOR
    config = PipelineConfigResponse(
        name="Constant Pipeline with Feature Extractor",
        slug="constant-with-feature-extractor",
        description=(
            "The constant pipeline, plus an 8-value feature vector for every detection "
            "from the constant feature extractor."
        ),
        version=1,
        algorithms=[
            algorithms.CONSTANT_DETECTOR,
            algorithms.CONSTANT_CLASSIFIER,
            algorithms.CONSTANT_FEATURE_EXTRACTOR,
        ],
    )


class FeatureExtractorOnlyPipeline(Pipeline):
    """Add feature vectors to detections without classifying them.

    Given detections, it returns each one unchanged (same box, same detector reference, same crop
    URL) with one vector attached and no classifications, so the caller can match them to the
    detections it sent. Without detections, it runs the constant detector first. Mirrors the AMI
    Data Companion's feature-only pipelines, which list a detector and an extractor.
    """

    feature_extractor = algorithms.CONSTANT_FEATURE_EXTRACTOR
    config = PipelineConfigResponse(
        name="Feature Extractor Only (constant)",
        slug="constant-feature-extractor-only",
        description=(
            "Return the detections it is sent, each with an 8-value feature vector and no classification. "
            "Detects with the constant detector when no detections are sent."
        ),
        version=1,
        algorithms=[
            algorithms.CONSTANT_DETECTOR,
            algorithms.CONSTANT_FEATURE_EXTRACTOR,
        ],
    )

    def resolve_extractor(self) -> AlgorithmConfigResponse | None:
        # Like the AMI Data Companion, a feature-only pipeline always runs its own extractor.
        return self.feature_extractor

    def run(self) -> list[DetectionResponse]:
        if self.existing_detections:
            logger.info("Using the detections sent with the request...")
            detections = self.existing_detections
        elif self.detections_sent:
            # Detecting here would return boxes the caller never sent and cannot match.
            logger.info("Every detection sent was skipped as empty; returning none.")
            detections = []
        else:
            logger.info("No detections sent, running the constant detector...")
            detections = make_constant_detection(self.source_images)
        return self.finish(
            [
                DetectionResponse(
                    source_image_id=detection.source_image.id,
                    bbox=detection.bbox,
                    algorithm=detection.algorithm,
                    crop_image_url=detection.crop_image_url,
                    timestamp=datetime.datetime.now(),
                    classifications=[],
                )
                for detection in detections
            ]
        )
