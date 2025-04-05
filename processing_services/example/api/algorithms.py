import datetime
import logging
import random

from .schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    DetectionResponse,
    SourceImage,
)
from .utils import get_image

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

SAVED_MODELS = {}


class Algorithm:
    algorithm_config_response: AlgorithmConfigResponse

    def __init__(self):
        if self.algorithm_config_response.key not in SAVED_MODELS:
            logger.info(f"Compiling {self.algorithm_config_response.key}...")
            self.compile()
        else:
            logger.info(f"Using existing model {self.algorithm_config_response.key}...")
            self.model = SAVED_MODELS[self.algorithm_config_response.key]

    def compile(self):
        raise NotImplementedError("Subclasses must implement the compile method")

    def run(self, inputs: list[SourceImage] | list[DetectionResponse]) -> list:
        raise NotImplementedError("Subclasses must implement the run method")

    algorithm_config_response = AlgorithmConfigResponse(
        name="Base Algorithm",
        key="base",
        task_type="base",
        description="A base class for all algorithms.",
        version=1,
        version_name="v1",
        category_map=None,
    )


class RandomLocalDetector(Algorithm):
    """
    A local detector that generates a single random bounding box.
    """

    def compile(self):
        pass

    def run(self, source_images: list[SourceImage]) -> list[DetectionResponse]:
        detector_responses: list[DetectionResponse] = []
        for source_image in source_images:
            if source_image.width and source_image.height:
                start_time = datetime.datetime.now()
                x1 = random.randint(0, source_image.width)
                x2 = random.randint(0, source_image.width)
                y1 = random.randint(0, source_image.height)
                y2 = random.randint(0, source_image.height)
                end_time = datetime.datetime.now()
                elapsed_time = (end_time - start_time).total_seconds()

                detector_responses.append(
                    DetectionResponse(
                        source_image_id=source_image.id,
                        bbox=BoundingBox(
                            x1=min(x1, x2),
                            y1=min(y1, y2),
                            x2=max(x1, x2),
                            y2=max(y1, y2),
                        ),
                        inference_time=elapsed_time,
                        algorithm=AlgorithmReference(
                            name=self.algorithm_config_response.name,
                            key=self.algorithm_config_response.key,
                        ),
                        timestamp=datetime.datetime.now(),
                        crop_image_url=source_image.url,
                    )
                )
            else:
                raise ValueError(f"Source image {source_image.id} does not have width and height attributes.")

        return detector_responses

    algorithm_config_response = AlgorithmConfigResponse(
        name="Random Local Detector",
        key="random-local-detector",
        task_type="detection",
        description="A detector that uses a random bounding box for each image.",
        version=1,
        version_name="v1",
        category_map=None,
    )


class ConstantLocalDetector(Algorithm):
    """
    A local detector that returns 2 constant bounding boxes for each image.
    """

    def compile(self):
        pass

    def run(self, source_images: list[SourceImage]) -> list[DetectionResponse]:
        detector_responses: list[DetectionResponse] = []
        for source_image in source_images:
            if source_image.width and source_image.height:
                start_time = datetime.datetime.now()
                x1 = source_image.width * 0.1
                x2 = source_image.width * 0.3
                y1 = source_image.height * 0.1
                y2 = source_image.height * 0.3
                end_time = datetime.datetime.now()
                elapsed_time = (end_time - start_time).total_seconds()

                detector_responses.append(
                    DetectionResponse(
                        source_image_id=source_image.id,
                        bbox=BoundingBox(
                            x1=min(x1, x2),
                            y1=min(y1, y2),
                            x2=max(x1, x2),
                            y2=max(y1, y2),
                        ),
                        inference_time=elapsed_time,
                        algorithm=AlgorithmReference(
                            name=self.algorithm_config_response.name,
                            key=self.algorithm_config_response.key,
                        ),
                        timestamp=datetime.datetime.now(),
                        crop_image_url=source_image.url,
                    )
                )

                start_time = datetime.datetime.now()
                x1 = source_image.width * 0.6
                x2 = source_image.width * 0.8
                y1 = source_image.height * 0.6
                y2 = source_image.height * 0.8
                end_time = datetime.datetime.now()
                elapsed_time = (end_time - start_time).total_seconds()

                detector_responses.append(
                    DetectionResponse(
                        source_image_id=source_image.id,
                        bbox=BoundingBox(
                            x1=min(x1, x2),
                            y1=min(y1, y2),
                            x2=max(x1, x2),
                            y2=max(y1, y2),
                        ),
                        inference_time=elapsed_time,
                        algorithm=AlgorithmReference(
                            name=self.algorithm_config_response.name,
                            key=self.algorithm_config_response.key,
                        ),
                        timestamp=datetime.datetime.now(),
                        crop_image_url=source_image.url,
                    )
                )
            else:
                raise ValueError(f"Source image {source_image.id} does not have width and height attributes.")

        return detector_responses

    algorithm_config_response = AlgorithmConfigResponse(
        name="Constant Local Detector",
        key="constant-local-detector",
        task_type="detection",
        description="A local detector that returns 2 constant bounding boxes for each image.",
        version=1,
        version_name="v1",
        category_map=None,
    )


class LocalClassifier(Algorithm):
    """
    A simple local classifier that uses the Hugging Face pipeline to classify images.
    """

    def compile(self):
        from transformers import pipeline

        self.model = pipeline(model="google/vit-base-patch16-224")
        SAVED_MODELS[self.algorithm_config_response.key] = self.model

    def run(self, detections: list[DetectionResponse]) -> list[DetectionResponse]:
        detections_to_return: list[DetectionResponse] = []
        for detection in detections:
            assert detection.crop_image_url is not None, "No crop image URL provided in detection."

        start_time = datetime.datetime.now()

        opened_cropped_images = [
            get_image(detection.crop_image_url, raise_exception=True) for detection in detections  # type: ignore
        ]

        # Process the entire batch of cropped images at once
        results = self.model(images=opened_cropped_images)

        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        for detection, preds in zip(detections, results):
            labels = [pred["label"] for pred in preds]
            scores = [pred["score"] for pred in preds]
            max_score_index = scores.index(max(scores))
            classification = labels[max_score_index]
            logger.info(f"Classification: {classification}")
            logger.info(f"labels: {labels}")
            logger.info(f"scores: {scores}")

            assert (
                detection.classifications is None or detection.classifications == []
            ), "Classifications should be empty or None before classification."

            detection_with_classification = detection.copy(deep=True)
            detection_with_classification.classifications = [
                ClassificationResponse(
                    classification=classification,
                    labels=labels,
                    scores=scores,
                    logits=scores,
                    inference_time=elapsed_time,
                    timestamp=datetime.datetime.now(),
                    algorithm=AlgorithmReference(
                        name=self.algorithm_config_response.name, key=self.algorithm_config_response.key
                    ),
                    terminal=True,
                )
            ]

            detections_to_return.append(detection_with_classification)

        return detections_to_return

    algorithm_config_response = AlgorithmConfigResponse(
        name="Local Classifier",
        key="local-classifier",
        task_type="classification",
        description="A vision transformer model for image classification.",
        version=1,
        version_name="v1",
        category_map=None,
    )
