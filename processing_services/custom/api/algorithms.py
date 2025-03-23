import datetime
import logging
import random

from .schemas import AlgorithmConfigResponse, AlgorithmReference, BoundingBox, ClassificationResponse, SourceImage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Algorithm:
    algorithm_config_response: AlgorithmConfigResponse

    def __init__(self):
        self.compile()

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

        logger.info("Sending bounding box...")

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

        self.vision_classifier = pipeline(model="google/vit-base-patch16-224")

    def run(self, source_image: SourceImage) -> list[ClassificationResponse]:
        source_image_url = """
        https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSzRC6TEW7daHfRIUJKbCPYkVJQjZTz2v5tIVJ18-VSKGahzUJ-ruBWAP7pTvVAvhQpQ2USJirQZuTu0XI1RG6oNg
        """

        # Define the algorithm compilation, execution
        preds = self.vision_classifier(images=source_image_url)

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
