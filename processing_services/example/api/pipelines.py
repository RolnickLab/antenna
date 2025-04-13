import datetime
import logging
from typing import final

from .algorithms import Algorithm, ConstantLocalizer, FlatBugLocalizer, HFImageClassifier, ZeroShotObjectDetector
from .exceptions import ClassificationError, DetectionError, LocalizationError
from .schemas import (
    Detection,
    DetectionResponse,
    PipelineConfigResponse,
    PipelineResultsResponse,
    SourceImage,
    SourceImageResponse,
)
from .utils import pipeline_stage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Pipeline:
    """
    A base class for defining and running a pipeline consisting of multiple stages.
    Each stage is represented by an algorithm that processes inputs and produces
    outputs. The pipeline is designed to handle batch processing using custom batch
    sizes for each stage.

    Attributes:
        stages (list[Algorithm]): A list of algorithms representing the stages of
        the pipeline in order of execution. Typically [Detector(), Classifier()].
        batch_sizes (list[int]): A list of integers specifying the batch size for
        each stage. For example, [1, 1] means that the detector can process 1
        source image a time and the classifier can process 1 detection at a time.
        config (PipelineConfigResponse): Pipeline metadata.
    """

    stages: list[Algorithm]
    batch_sizes: list[int]
    config: PipelineConfigResponse

    config = PipelineConfigResponse(
        name="Base Pipeline",
        slug="base",
        description="A base class for all pipelines.",
        version=1,
        algorithms=[],
    )

    def __init__(self, source_images: list[SourceImage], custom_batch_sizes: list[int] = []):
        self.source_images = source_images
        if custom_batch_sizes:
            self.batch_sizes = custom_batch_sizes
        if not self.batch_sizes:
            self.batch_sizes = [1] * len(self.stages)

        assert len(self.batch_sizes) == len(self.stages), "Number of batch sizes must match the number of stages."

    def run(self) -> PipelineResultsResponse:
        """
        When subclassing, you can override this function to change the order
        of the stages or add additional stages. Stages are functions with the
        @pipeline_stage decorator.

        This function must always return a PipelineResultsResponse object.
        """
        start_time = datetime.datetime.now()
        detections: list[Detection] = self._get_detections(self.source_images)
        detections_with_classifications: list[Detection] = self._get_detections_with_classifications(detections)
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(
            detections_with_classifications, elapsed_time
        )

        return pipeline_response

    @final
    def _batchify_inputs(self, inputs: list, batch_size: int) -> list[list]:
        """
        Helper funfction to split the inputs into batches of the specified size.
        """
        batched_inputs = []
        for i in range(0, len(inputs), batch_size):
            start_id = i
            end_id = i + batch_size
            batched_inputs.append(inputs[start_id:end_id])
        return batched_inputs

    @pipeline_stage(stage_index=0, error_type=LocalizationError)
    def _get_detections(self, source_images: list[SourceImage], **kwargs) -> list[Detection]:
        logger.info("Running detector...")
        stage_index = kwargs.get("stage_index")

        detector = self.stages[stage_index]  # type: ignore
        detections: list[Detection] = []

        batched_source_images = self._batchify_inputs(source_images, self.batch_sizes[stage_index])  # type: ignore

        for batch in batched_source_images:
            detections.extend(detector.run(batch))

        return detections

    @pipeline_stage(stage_index=1, error_type=ClassificationError)
    def _get_detections_with_classifications(self, detections: list[Detection], **kwargs) -> list[Detection]:
        logger.info("Running classifier...")
        stage_index = kwargs.get("stage_index")

        classifier = self.stages[stage_index]  # type: ignore
        detections_with_classifications: list[Detection] = []

        batched_detections = self._batchify_inputs(detections, self.batch_sizes[stage_index])  # type: ignore

        for batch in batched_detections:
            detections_with_classifications.extend(classifier.run(batch))

        return detections_with_classifications

    @final
    def _get_pipeline_response(self, detections: list[Detection], elapsed_time: float) -> PipelineResultsResponse:
        """
        Final stage of the pipeline to format the detections.
        """
        detection_responses = [
            DetectionResponse(
                source_image_id=detection.source_image.id,
                bbox=detection.bbox,
                inference_time=detection.inference_time,
                algorithm=detection.algorithm,
                timestamp=datetime.datetime.now(),
                classifications=detection.classifications,
            )
            for detection in detections
        ]
        source_image_responses = [SourceImageResponse(**image.model_dump()) for image in self.source_images]

        return PipelineResultsResponse(
            pipeline=self.config.slug,  # type: ignore
            algorithms={algorithm.key: algorithm for algorithm in self.config.algorithms},
            total_time=elapsed_time,
            source_images=source_image_responses,
            detections=detection_responses,
        )


class ConstantDetectionPipeline(Pipeline):
    """
    A pipeline that generates 2 constant bounding boxes and applies a HuggingFace image classifier.
    """

    stages = [ConstantLocalizer(), HFImageClassifier()]
    batch_sizes = [1, 1]
    config = PipelineConfigResponse(
        name="Constant Detection Pipeline",
        slug="constant-detection-pipeline",
        description=("2 constant bounding boxes with HF image classifier."),
        version=1,
        algorithms=[stage.algorithm_config_response for stage in stages],
    )


class ZeroShotObjectDetectorPipeline(Pipeline):
    """
    A pipeline that uses the HuggingFace zero shot object detector.
    """

    stages = [ZeroShotObjectDetector()]
    batch_sizes = [1]
    config = PipelineConfigResponse(
        name="Zero Shot Object Detector Pipeline",
        slug="zero-shot-object-detector-pipeline",
        description=("HF zero shot object detector."),
        version=1,
        algorithms=[stage.algorithm_config_response for stage in stages],
    )

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections_with_classifications: list[Detection] = self._get_detections_with_classifications(
            self.source_images
        )
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(
            detections_with_classifications, elapsed_time
        )

        return pipeline_response

    @pipeline_stage(stage_index=0, error_type=DetectionError)
    def _get_detections_with_classifications(self, source_images: list[SourceImage], **kwargs) -> list[Detection]:
        logger.info("Running zero shot object detector...")
        stage_index = kwargs.get("stage_index")

        zero_shot_detector = self.stages[stage_index]  # type: ignore
        detections_with_classifications: list[Detection] = []

        batched_images = self._batchify_inputs(source_images, self.batch_sizes[stage_index])  # type: ignore

        for batch in batched_images:
            detections_with_classifications.extend(zero_shot_detector.run(batch))

        return detections_with_classifications


class FlatBugDetectorPipeline(Pipeline):
    """
    A pipeline that uses the Darsa Group's flat bug detector. No classifications.
    """

    stages = [FlatBugLocalizer()]
    batch_sizes = [1]
    config = PipelineConfigResponse(
        name="Flat Bug Detector Pipeline",
        slug="flat-bug-detector-pipeline",
        description=(
            "DARSA Group: Flatbug is a hyperinference and trained YOLOv8 model zoo, "
            "with a bespoke diverse dataset of the same name."
        ),
        version=1,
        algorithms=[stage.algorithm_config_response for stage in stages],
    )

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        # Only return detections with no classification
        detections: list[Detection] = self._get_detections(self.source_images)
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(detections, elapsed_time)

        return pipeline_response
