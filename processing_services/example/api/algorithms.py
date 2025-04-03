import datetime
import logging
import random

from .schemas import AlgorithmConfigResponse, AlgorithmReference, BoundingBox, ClassificationResponse, SourceImage

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

    def run(self) -> list:
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


class LocalDetector(Algorithm):
    """
    A simple local detector that uses a constant bounding box for each image.
    """

    def compile(self):
        pass

    def run(self, source_image: SourceImage) -> list[BoundingBox]:
        x1 = random.randint(0, source_image.width)
        x2 = random.randint(0, source_image.width)
        y1 = random.randint(0, source_image.height)
        y2 = random.randint(0, source_image.height)

        logger.info("Sending bounding box with coordinates {x1}, {y1}, {x2}, {y2}...")

        return [
            BoundingBox(
                x1=min(x1, x2),
                y1=min(y1, y2),
                x2=max(x1, x2),
                y2=max(y1, y2),
            )
        ]

    algorithm_config_response = AlgorithmConfigResponse(
        name="Local Detector",
        key="local-detector",
        task_type="detection",
        description="A detector that uses a random bounding box for each image.",
        version=1,
        version_name="v1",
        category_map=None,
    )


class ConstantDetector(Algorithm):
    """
    A simple local detector that uses a constant bounding box for each image.
    """

    def compile(self):
        pass

    def run(self, source_image: SourceImage) -> list[BoundingBox]:
        x1 = source_image.width * 0.25
        x2 = source_image.width * 0.75
        y1 = source_image.height * 0.25
        y2 = source_image.height * 0.75

        logger.info(f"Sending bounding box with coordinates {x1}, {y1}, {x2}, {y2}...")

        return [
            BoundingBox(
                x1=min(x1, x2),
                y1=min(y1, y2),
                x2=max(x1, x2),
                y2=max(y1, y2),
            )
        ]

    algorithm_config_response = AlgorithmConfigResponse(
        name="Constant Detector",
        key="constant-detector",
        task_type="detection",
        description="A detector that uses a constant bounding box for each image.",
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

    def run(self, source_image: SourceImage) -> list[ClassificationResponse]:
        # Define the algorithm compilation, execution
        preds = self.model(images=source_image._pil)

        labels = [pred["label"] for pred in preds]
        scores = [pred["score"] for pred in preds]
        max_score_index = scores.index(max(scores))
        classification = labels[max_score_index]
        logger.info(f"Classification: {classification}")
        logger.info(f"labels: {labels}")
        logger.info(f"scores: {scores}")
        logger.info("Sending classification response...")

        return [
            ClassificationResponse(
                classification=classification,
                labels=labels,
                scores=scores,
                logits=scores,
                timestamp=datetime.datetime.now(),
                algorithm=AlgorithmReference(
                    name=self.algorithm_config_response.name, key=self.algorithm_config_response.key
                ),
                terminal=True,
            )
        ]

    algorithm_config_response = AlgorithmConfigResponse(
        name="Local Classifier",
        key="local-classifier",
        task_type="classification",
        description="A vision transformer model for image classification.",
        version=1,
        version_name="v1",
        category_map=None,
    )
