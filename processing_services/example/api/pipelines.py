import datetime
import logging
from typing import final

from .algorithms import (
    Algorithm,
    ConstantClassifier,
    HFImageClassifier,
    RandomSpeciesClassifier,
    ZeroShotObjectDetector,
)
from .global_moth_classifier import GlobalMothClassifier
from .schemas import (
    Detection,
    DetectionResponse,
    PipelineConfigResponse,
    PipelineRequestConfigParameters,
    PipelineResultsResponse,
    SourceImage,
    SourceImageResponse,
)

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
        request_config: PipelineRequestConfigParameters | dict = {},
        existing_detections: list[Detection] = [],
        custom_batch_sizes: list[int] = [],
    ):
        self.source_images = source_images
        self.request_config = request_config if isinstance(request_config, dict) else request_config.model_dump()
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
        self, algorithm: Algorithm, inputs: list[SourceImage] | list[Detection], batch_size: int, **kwargs
    ) -> list[Detection]:
        """A single stage, step, or algorithm in a pipeline. Batchifies inputs and produces Detections as outputs."""
        outputs: list[Detection] = []
        batched_inputs = self._batchify_inputs(inputs, batch_size)
        for batch in batched_inputs:
            outputs.extend(algorithm.run(batch, **kwargs))
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
            # algorithms={algorithm.key: algorithm for algorithm in self.config.algorithms},
            total_time=elapsed_time,
            source_images=source_image_responses,
            detections=detection_responses,
        )


class ZeroShotHFClassifierPipeline(Pipeline):
    """
    A pipeline that uses the Zero Shot Object Detector to produce bounding boxes
    and then applies the HuggingFace image classifier.
    """

    batch_sizes = [1, 1]
    config = PipelineConfigResponse(
        name="Zero Shot HF Classifier Pipeline",
        slug="zero-shot-hf-classifier-pipeline",
        description=("Zero Shot Object Detector with HF image classifier."),
        version=1,
        algorithms=[
            ZeroShotObjectDetector().algorithm_config_response,
            HFImageClassifier().algorithm_config_response,
        ],
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            logger.info(
                "Setting candidate labels for zero shot object detector to %s", self.request_config["candidate_labels"]
            )
            zero_shot_object_detector.candidate_labels = self.request_config["candidate_labels"]
        self.config.algorithms = [
            zero_shot_object_detector.algorithm_config_response,
            HFImageClassifier().algorithm_config_response,
        ]

        return [zero_shot_object_detector, HFImageClassifier()]

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections_with_candidate_labels: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections_with_candidate_labels = self.existing_detections
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections_with_candidate_labels: list[Detection] = self._get_detections(
                self.stages[0], self.source_images, self.batch_sizes[0], intermediate=True
            )

        logger.info("[2/2] Running the classifier...")
        detections_with_classifications: list[Detection] = self._get_detections(
            self.stages[1], detections_with_candidate_labels, self.batch_sizes[1]
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
    Produces both a bounding box and a classification for each detection.
    The classification is based on the candidate labels provided in the request.
    """

    batch_sizes = [1]
    config = PipelineConfigResponse(
        name="Zero Shot Object Detector Pipeline",
        slug="zero-shot-object-detector-pipeline",
        description=("Zero shot object detector (bbox and classification)."),
        version=1,
        algorithms=[ZeroShotObjectDetector().algorithm_config_response],
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            logger.info(
                "Setting candidate labels for zero shot object detector to %s", self.request_config["candidate_labels"]
            )
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
            ZeroShotObjectDetector().algorithm_config_response,
            RandomSpeciesClassifier().algorithm_config_response,
        ],
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            zero_shot_object_detector.candidate_labels = self.request_config["candidate_labels"]

        self.config.algorithms = [
            zero_shot_object_detector.algorithm_config_response,
            RandomSpeciesClassifier().algorithm_config_response,
        ]

        return [zero_shot_object_detector, RandomSpeciesClassifier()]

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections = self.existing_detections
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
            ZeroShotObjectDetector().algorithm_config_response,
            ConstantClassifier().algorithm_config_response,
        ],
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            zero_shot_object_detector.candidate_labels = self.request_config["candidate_labels"]

        self.config.algorithms = [
            zero_shot_object_detector.algorithm_config_response,
            ConstantClassifier().algorithm_config_response,
        ]

        return [zero_shot_object_detector, ConstantClassifier()]

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections: list[Detection] = []
        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections = self.existing_detections
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


class ZeroShotObjectDetectorWithGlobalMothClassifierPipeline(Pipeline):
    """
    A pipeline that uses the HuggingFace zero shot object detector and the global moth classifier.
    This provides high-quality moth species identification with 29,176+ species support.
    """

    batch_sizes = [1, 4]  # Detector batch=1, Classifier batch=4
    config = PipelineConfigResponse(
        name="Zero Shot Object Detector With Global Moth Classifier Pipeline",
        slug="zero-shot-object-detector-with-global-moth-classifier-pipeline",
        description=(
            "HF zero shot object detector with global moth species classifier. "
            "Supports 29,176+ moth species trained on global data."
        ),
        version=1,
        algorithms=[],  # Will be populated in get_stages()
    )

    def get_stages(self) -> list[Algorithm]:
        zero_shot_object_detector = ZeroShotObjectDetector()
        if "candidate_labels" in self.request_config:
            zero_shot_object_detector.candidate_labels = self.request_config["candidate_labels"]

        global_moth_classifier = GlobalMothClassifier()

        self.config.algorithms = [
            zero_shot_object_detector.algorithm_config_response,
            global_moth_classifier.algorithm_config_response,
        ]

        return [zero_shot_object_detector, global_moth_classifier]

    def run(self) -> PipelineResultsResponse:
        start_time = datetime.datetime.now()
        detections: list[Detection] = []

        if self.existing_detections:
            logger.info("[1/2] Skipping the localizer, use existing detections...")
            detections = self.existing_detections
        else:
            logger.info("[1/2] No existing detections, generating detections...")
            detections = self._get_detections(self.stages[0], self.source_images, self.batch_sizes[0])

        logger.info("[2/2] Running the global moth classifier...")
        detections_with_classifications: list[Detection] = self._get_detections(
            self.stages[1], detections, self.batch_sizes[1]
        )

        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        pipeline_response: PipelineResultsResponse = self._get_pipeline_response(
            detections_with_classifications, elapsed_time
        )
        logger.info(
            f"Successfully processed {len(detections_with_classifications)} detections with global moth classifier."
        )

        return pipeline_response
