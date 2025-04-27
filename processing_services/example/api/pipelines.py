import datetime
import logging
from typing import final

from .algorithms import (
    Algorithm,
    ConstantClassifier,
    ConstantLocalizer,
    FlatBugLocalizer,
    HFImageClassifier,
    RandomSpeciesClassifier,
    ZeroShotObjectDetector,
)
from .schemas import (
    Detection,
    DetectionResponse,
    PipelineConfigResponse,
    PipelineResultsResponse,
    SourceImage,
    SourceImageResponse,
)
from .utils import get_image

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
    request_config: dict
    config: PipelineConfigResponse

    stages = []
    batch_sizes = []
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
        request_config: dict = {},
        existing_detections: list[Detection] = [],
        custom_batch_sizes: list[int] = [],
    ):
        self.source_images = source_images
        self.request_config = request_config
        self.existing_detections = existing_detections

        logger.info("Initializing algorithms....")
        self.stages = self.stages or self.get_stages()
        self.batch_sizes = custom_batch_sizes or self.batch_sizes or [1] * len(self.stages)
        assert len(self.batch_sizes) == len(self.stages), "Number of batch sizes must match the number of stages."

    def get_stages(self) -> list[Algorithm]:
        """
        An optional function to initialize and return a list of algorithms/stages.
        Any pipeline config values relevant to a particular algorithm should be passed or set here.
        """
        return []

    @final
    def compile(self):
        logger.info("Compiling algorithms....")
        for stage_idx, stage in enumerate(self.stages):
            logger.info(f"[{stage_idx+1}/{len(self.stages)}] Compiling {stage.algorithm_config_response.name}...")
            stage.compile()

    def run(self) -> PipelineResultsResponse:
        """
        This function must always return a PipelineResultsResponse object.
        """
        raise NotImplementedError("Subclasses must implement")

    @final
    def _batchify_inputs(self, inputs: list, batch_size: int) -> list[list]:
        """
        Helper function to split the inputs into batches of the specified size.
        """
        batched_inputs = []
        for i in range(0, len(inputs), batch_size):
            start_id = i
            end_id = i + batch_size
            batched_inputs.append(inputs[start_id:end_id])
        return batched_inputs

    @final
    def _get_detections(
        self, algorithm: Algorithm, inputs: list[SourceImage] | list[Detection], batch_size: int
    ) -> list[Detection]:
        """A single stage, step, or algorithm in a pipeline. Batchifies inputs and produces Detections as outputs."""
        outputs: list[Detection] = []
        batched_inputs = self._batchify_inputs(inputs, batch_size)  # type: ignore
        for batch in batched_inputs:
            outputs.extend(algorithm.run(batch))
        return outputs

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

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections = self._process_existing_detections()
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections = self._get_detections(self.stages[0], self.source_images, self.batch_sizes[0])

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[Detection] = self._get_detections(
            self.stages[1], detections, self.batch_sizes[1]
        )
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(
            detections_with_classifications, elapsed_time
        )
        logger.info(f"Successfully processed {len(detections_with_classifications)} detections.")

        return pipeline_response


class ZeroShotObjectDetectorPipeline(Pipeline):
    """
    A pipeline that uses the HuggingFace zero shot object detector.
    """

    batch_sizes = [1]
    config = PipelineConfigResponse(
        name="Zero Shot Object Detector Pipeline",
        slug="zero-shot-object-detector-pipeline",
        description=("HF zero shot object detector."),
        version=1,
        algorithms=[ZeroShotObjectDetector.algorithm_config_response],
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            zero_shot_object_detector.candidate_labels = self.request_config["candidate_labels"]

        self.config.algorithms = [zero_shot_object_detector.algorithm_config_response]

        return [zero_shot_object_detector]

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        logger.info("[1/1] Running the zero shot object detector...")
        detections_with_classifications: list[Detection] = self._get_detections(
            self.stages[0], self.source_images, self.batch_sizes[0]
        )
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(
            detections_with_classifications, elapsed_time
        )
        logger.info(f"Successfully processed {len(detections_with_classifications)} detections.")

        return pipeline_response


class ZeroShotObjectDetectorWithRandomSpeciesClassifierPipeline(Pipeline):
    """
    A pipeline that uses the HuggingFace zero shot object detector and a random species classifier.
    """

    batch_sizes = [1, 1]
    config = PipelineConfigResponse(
        name="Zero Shot Object Detector With Random Species Classifier Pipeline",
        slug="zero-shot-object-detector-with-random-species-classifier-pipeline",
        description=("HF zero shot object detector with random species classifier."),
        version=1,
        algorithms=[
            ZeroShotObjectDetector.algorithm_config_response,
            RandomSpeciesClassifier.algorithm_config_response,
        ],
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            zero_shot_object_detector.candidate_labels = self.request_config["candidate_labels"]

        self.config.algorithms = [
            zero_shot_object_detector.algorithm_config_response,
            RandomSpeciesClassifier.algorithm_config_response,
        ]

        return [zero_shot_object_detector, RandomSpeciesClassifier()]

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections = self._process_existing_detections()
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections = self._get_detections(self.stages[0], self.source_images, self.batch_sizes[0])

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[Detection] = self._get_detections(
            self.stages[1], detections, self.batch_sizes[1]
        )
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(
            detections_with_classifications, elapsed_time
        )
        logger.info(f"Successfully processed {len(detections_with_classifications)} detections.")

        return pipeline_response


class ZeroShotObjectDetectorWithConstantClassifierPipeline(Pipeline):
    """
    A pipeline that uses the HuggingFace zero shot object detector and a constant classifier.
    """

    batch_sizes = [1, 1]
    config = PipelineConfigResponse(
        name="Zero Shot Object Detector With Constant Classifier Pipeline",
        slug="zero-shot-object-detector-with-constant-classifier-pipeline",
        description=("HF zero shot object detector with constant classifier."),
        version=1,
        algorithms=[
            ZeroShotObjectDetector.algorithm_config_response,
            ConstantClassifier.algorithm_config_response,
        ],
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            zero_shot_object_detector.candidate_labels = self.request_config["candidate_labels"]

        self.config.algorithms = [
            zero_shot_object_detector.algorithm_config_response,
            ConstantClassifier.algorithm_config_response,
        ]

        return [zero_shot_object_detector, ConstantClassifier()]

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections = self._process_existing_detections()
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections = self._get_detections(self.stages[0], self.source_images, self.batch_sizes[0])

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[Detection] = self._get_detections(
            self.stages[1], detections, self.batch_sizes[1]
        )
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(
            detections_with_classifications, elapsed_time
        )
        logger.info(f"Successfully processed {len(detections_with_classifications)} detections.")

        return pipeline_response


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
        logger.info("[1/1] Running the flat bug detector...")
        detections: list[Detection] = self._get_detections(self.stages[0], self.source_images, self.batch_sizes[0])
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(detections, elapsed_time)
        logger.info(f"Successfully processed {len(detections)} detections.")

        return pipeline_response
