import logging

from .algorithms import Algorithm, ConstantLocalDetector, LocalClassifier, RandomLocalDetector
from .schemas import DetectionResponse, PipelineConfigResponse, SourceImage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Pipeline:
    stages: list[Algorithm]
    config: PipelineConfigResponse

    def __init__(self, source_images: list[SourceImage], detector_batch_size: int = 1, classifier_batch_size: int = 1):
        self.source_images = source_images
        self.detector_batch_size = detector_batch_size
        self.classifier_batch_size = classifier_batch_size

    def run(self) -> list[DetectionResponse]:
        batched_images: list[list[SourceImage]] = []
        for i in range(0, len(self.source_images), self.detector_batch_size):
            start_id = i
            end_id = i + self.detector_batch_size
            batched_images.append(self.source_images[start_id:end_id])
        detector_outputs: list[DetectionResponse] = []
        for images in batched_images:
            detector_outputs.extend(self.get_detector_response(images))

        classifier_batched_inputs: list[list[DetectionResponse]] = []
        for i in range(0, len(detector_outputs), self.classifier_batch_size):
            start_id = i
            end_id = i + self.classifier_batch_size
            batch = detector_outputs[start_id:end_id]
            classifier_batched_inputs.append(batch)
        detections: list[DetectionResponse] = []
        for detector_responses in classifier_batched_inputs:
            detections.extend(self.get_classifier_response(detector_responses))

        return detections

    def get_detector_response(self, source_images: list[SourceImage]) -> list[DetectionResponse]:
        logger.info("Running detector...")
        detector = self.stages[0]
        for image in source_images:
            image.open(raise_exception=True)
        detector_results: list[DetectionResponse] = detector.run(source_images)
        return detector_results

    def get_classifier_response(self, input_detections: list[DetectionResponse]) -> list[DetectionResponse]:
        logger.info("Running classifier...")
        classifier = self.stages[1]
        detections: list[DetectionResponse] = classifier.run(input_detections)
        return detections

    config = PipelineConfigResponse(
        name="Base Pipeline",
        slug="base",
        description="A base class for all pipelines.",
        version=1,
        algorithms=[],
    )


class CustomPipeline(Pipeline):
    """
    Demo: A pipeline that uses a single bbox random detector and a local classifier.
    """

    stages = [RandomLocalDetector(), LocalClassifier()]
    config = PipelineConfigResponse(
        name="Local Pipeline",
        slug="local-pipeline",
        description=("Transformers whole image classification."),
        version=1,
        algorithms=[stage.algorithm_config_response for stage in stages],
    )


class ConstantDetectorClassification(Pipeline):
    """
    Demo: A pipeline that uses a double bbox constant detector and a local classifier.
    """

    stages = [ConstantLocalDetector(), LocalClassifier()]
    config = PipelineConfigResponse(
        name="Constant Detector Classifier Pipeline",
        slug="constant-detector-classifier-pipeline",
        description=("A demo pipeline using a new detector."),
        version=1,
        algorithms=[stage.algorithm_config_response for stage in stages],
    )
