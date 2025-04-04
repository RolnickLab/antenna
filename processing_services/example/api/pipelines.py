import datetime
import logging

from .algorithms import Algorithm, ConstantDetector, LocalClassifier, LocalDetector
from .schemas import (
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    PipelineConfigResponse,
    SourceImage,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Pipeline:
    stages: list[Algorithm]
    config: PipelineConfigResponse

    def __init__(self, source_images: list[SourceImage]):
        self.source_images = source_images

    def run(self) -> list[DetectionResponse]:
        results = [self.make_detections(source_image) for source_image in self.source_images]
        # Flatten the list of lists
        return [item for sublist in results for item in sublist]

    def make_detections(self, source_image: SourceImage) -> list[DetectionResponse]:
        raise NotImplementedError("Subclasses must implement the make_detections")

    config = PipelineConfigResponse(
        name="Base Pipeline",
        slug="base",
        description="A base class for all pipelines.",
        version=1,
        algorithms=[],
    )


class CustomPipeline(Pipeline):
    """
    Define a custom pipeline so that the outputs from each algorithm can be correctly processed to produce detections.
    """

    def make_detections(self, source_image: SourceImage) -> list[DetectionResponse]:
        logger.info("Making detections...")
        source_image.open(raise_exception=True)

        assert source_image.width is not None and source_image.height is not None

        # For this pipeline, the 1 bbox is always returned
        logger.info("Running detector...")
        bboxes: list[BoundingBox] = self.stages[0].run(source_image)

        logger.info("Running classifier...")
        classifications: list[ClassificationResponse] = self.stages[1].run(source_image)

        return [
            DetectionResponse(
                source_image_id=source_image.id,
                bbox=bbox,
                timestamp=datetime.datetime.now(),
                algorithm=AlgorithmReference(name=self.config.algorithms[0].name, key=self.config.algorithms[0].key),
                classifications=classifications,
            )
            for bbox in bboxes
        ]

    stages = [LocalDetector(), LocalClassifier()]
    config = PipelineConfigResponse(
        name="Local Pipeline",
        slug="local-pipeline",
        description=("Transformers whole image classification."),
        version=1,
        algorithms=[stage.algorithm_config_response for stage in stages],
    )


class ConstantDetectorClassification(Pipeline):
    """
    Demo
    """

    def make_detections(self, source_image: SourceImage) -> list[DetectionResponse]:
        logger.info("Making detections...")
        source_image.open(raise_exception=True)

        assert source_image.width is not None and source_image.height is not None

        # For this pipeline, the 1 bbox is always returned
        try:
            bboxes: list[BoundingBox] = self.stages[0].run(source_image)
        except Exception as e:
            logger.error(f"Error running detector: {e}")

        try:
            classifications: list[ClassificationResponse] = self.stages[1].run(source_image)
        except Exception as e:
            logger.error(f"Error running classifier: {e}")

        return [
            DetectionResponse(
                source_image_id=source_image.id,
                bbox=bbox,
                timestamp=datetime.datetime.now(),
                algorithm=AlgorithmReference(name=self.config.algorithms[0].name, key=self.config.algorithms[0].key),
                classifications=classifications,
            )
            for bbox in bboxes
        ]

    stages = [ConstantDetector(), LocalClassifier()]
    config = PipelineConfigResponse(
        name="Constant Detector Classifier Pipeline",
        slug="constant-detector-classifier-pipeline",
        description=("A demo pipeline using a new detector."),
        version=1,
        algorithms=[stage.algorithm_config_response for stage in stages],
    )
