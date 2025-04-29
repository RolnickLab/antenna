import datetime
import logging
import math
import random

import torch

from .schemas import (
    AlgorithmCategoryMapResponse,
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    Detection,
    SourceImage,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

SAVED_MODELS = {}


def get_best_device() -> str:
    """
    Returns the best available device for running the model.

    MPS is not supported by the current algoritms.
    """
    if torch.cuda.is_available():
        return f"cuda:{torch.cuda.current_device()}"
    else:
        return "cpu"


class Algorithm:
    algorithm_config_response: AlgorithmConfigResponse

    def compile(self):
        raise NotImplementedError("Subclasses must implement the compile method")

    def run(self, inputs: list[SourceImage] | list[Detection]) -> list[Detection]:
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


class ZeroShotObjectDetector(Algorithm):
    """
    Huggingface Zero-Shot Object Detection model.
    Produces both a bounding box and a classification for each detection.
    The classification is based on the candidate labels.
    """

    candidate_labels: list[str] = ["insect"]

    def compile(self, device: str | None = None):
        saved_models_key = "zero_shot_object_detector"  # generate a key for each uniquely compiled algorithm

        if saved_models_key not in SAVED_MODELS:
            from transformers import pipeline

            device_choice = device or get_best_device()
            device_index = int(device_choice.split(":")[-1]) if ":" in device_choice else -1
            logger.info(f"Compiling {self.algorithm_config_response.name} on device {device_choice}...")
            checkpoint = "google/owlv2-base-patch16-ensemble"
            self.model = pipeline(
                model=checkpoint,
                task="zero-shot-object-detection",
                use_fast=True,
                device=device_index,
            )
            SAVED_MODELS[saved_models_key] = self.model
        else:
            logger.info(f"Using saved model for {self.algorithm_config_response.name}...")
            self.model = SAVED_MODELS[saved_models_key]

    def run(self, source_images: list[SourceImage], intermediate=False) -> list[Detection]:
        detector_responses: list[Detection] = []
        for source_image in source_images:
            source_image.open(raise_exception=True)

            if source_image.width and source_image.height and source_image._pil:
                start_time = datetime.datetime.now()
                logger.info("Predicting...")
                if not self.candidate_labels:
                    raise ValueError("No candidate labels are provided during inference.")
                logger.info(f"Predicting with candidate labels: {self.candidate_labels}")
                predictions = self.model(source_image._pil, candidate_labels=self.candidate_labels)
                end_time = datetime.datetime.now()
                elapsed_time = (end_time - start_time).total_seconds()

                for prediction in predictions:
                    logger.info("Prediction: %s", prediction)
                    bbox = BoundingBox(
                        x1=prediction["box"]["xmin"],
                        x2=prediction["box"]["xmax"],
                        y1=prediction["box"]["ymin"],
                        y2=prediction["box"]["ymax"],
                    )
                    cropped_image_pil = source_image._pil.crop((bbox.x1, bbox.y1, bbox.x2, bbox.y2))
                    detection = Detection(
                        id=f"{source_image.id}-crop-{bbox.x1}-{bbox.y1}-{bbox.x2}-{bbox.y2}",
                        url=source_image.url,  # @TODO: ideally, should save cropped image at separate url
                        width=cropped_image_pil.width,
                        height=cropped_image_pil.height,
                        timestamp=datetime.datetime.now(),
                        source_image=source_image,
                        bbox=bbox,
                        inference_time=elapsed_time,
                        algorithm=AlgorithmReference(
                            name=self.algorithm_config_response.name,
                            key=self.algorithm_config_response.key,
                        ),
                        classifications=[
                            ClassificationResponse(
                                classification=prediction["label"],
                                labels=[prediction["label"]],
                                scores=[prediction["score"]],
                                logits=[prediction["score"]],
                                inference_time=elapsed_time,
                                timestamp=datetime.datetime.now(),
                                algorithm=AlgorithmReference(
                                    name=self.algorithm_config_response.name,
                                    key=self.algorithm_config_response.key,
                                ),
                                terminal=not intermediate,
                            )
                        ],
                    )
                    detection._pil = cropped_image_pil
                    detector_responses.append(detection)
            else:
                raise ValueError(f"Source image {source_image.id} does not have width and height attributes.")

        return detector_responses

    algorithm_config_response = AlgorithmConfigResponse(
        name="Zero Shot Object Detector",
        key="zero-shot-object-detector",
        task_type="detection",
        description=(
            "Huggingface Zero Shot Object Detection model."
            "Produces both a bounding box and a candidate label classification for each detection."
        ),
        version=1,
        version_name="v1",
        category_map=None,
    )


class HFImageClassifier(Algorithm):
    """
    A  local classifier that uses the Hugging Face pipeline to classify images.
    """

    def compile(self):
        saved_models_key = "hf_image_classifier"  # generate a key for each uniquely compiled algorithm

        if saved_models_key not in SAVED_MODELS:
            from transformers import pipeline

            logger.info(f"Compiling {self.algorithm_config_response.name} from scratch...")
            self.model = pipeline("image-classification", model="google/vit-base-patch16-224")
            SAVED_MODELS[saved_models_key] = self.model
        else:
            logger.info(f"Using saved model for {self.algorithm_config_response.name}...")
            self.model = SAVED_MODELS[saved_models_key]

    def run(self, detections: list[Detection]) -> list[Detection]:
        detections_to_return: list[Detection] = []
        start_time = datetime.datetime.now()

        opened_cropped_images = [detection._pil for detection in detections]  # type: ignore

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

            existing_classifications = detection.classifications

            detection_with_classification = detection.copy(deep=True)
            detection_with_classification.classifications = existing_classifications + [
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
        name="HF Image Classifier",
        key="hf-image-classifier",
        task_type="classification",
        description="HF ViT for image classification.",
        version=1,
        version_name="v1",
        category_map=None,
    )


class RandomSpeciesClassifier(Algorithm):
    """
    A local classifier that produces random butterfly species classifications.
    """

    def compile(self):
        pass

    def _make_random_prediction(
        self,
        terminal: bool = True,
        max_labels: int = 2,
    ) -> ClassificationResponse:
        assert self.algorithm_config_response.category_map is not None
        category_labels = self.algorithm_config_response.category_map.labels
        logits = [random.random() for _ in category_labels]
        softmax = [math.exp(logit) / sum([math.exp(logit) for logit in logits]) for logit in logits]
        top_class = category_labels[softmax.index(max(softmax))]
        return ClassificationResponse(
            classification=top_class,
            labels=category_labels if len(category_labels) <= max_labels else None,
            scores=softmax,
            logits=logits,
            timestamp=datetime.datetime.now(),
            algorithm=AlgorithmReference(
                name=self.algorithm_config_response.name,
                key=self.algorithm_config_response.key,
            ),
            terminal=terminal,
        )

    def run(self, detections: list[Detection]) -> list[Detection]:
        detections_to_return: list[Detection] = []
        for detection in detections:
            detection_with_classification = detection.copy(deep=True)
            detection_with_classification.classifications = [self._make_random_prediction(terminal=True)]
            detections_to_return.append(detection_with_classification)
        return detections_to_return

    algorithm_config_response = AlgorithmConfigResponse(
        name="Random species classifier",
        key="random-species-classifier",
        task_type="classification",
        description="A random species classifier",
        version=1,
        version_name="v1",
        uri="https://huggingface.co/RolnickLab/random-species-classifier",
        category_map=AlgorithmCategoryMapResponse(
            data=[
                {
                    "index": 0,
                    "gbif_key": "1234",
                    "label": "Vanessa atalanta",
                    "source": "manual",
                    "taxon_rank": "SPECIES",
                },
                {
                    "index": 1,
                    "gbif_key": "4543",
                    "label": "Vanessa cardui",
                    "source": "manual",
                    "taxon_rank": "SPECIES",
                },
                {
                    "index": 2,
                    "gbif_key": "7890",
                    "label": "Vanessa itea",
                    "source": "manual",
                    "taxon_rank": "SPECIES",
                },
            ],
            labels=["Vanessa atalanta", "Vanessa cardui", "Vanessa itea"],
            version="v1",
            description="A simple species classifier",
            uri="https://huggingface.co/RolnickLab/random-species-classifier",
        ),
    )


class ConstantClassifier(Algorithm):
    """
    A local classifier that always returns a constant species classification.
    """

    def compile(self):
        pass

    def _make_constant_prediction(
        self,
        terminal: bool = True,
    ) -> ClassificationResponse:
        assert self.algorithm_config_response.category_map is not None
        labels = self.algorithm_config_response.category_map.labels
        return ClassificationResponse(
            classification=labels[0],
            labels=labels,
            scores=[0.9],  # Constant score for each detection
            timestamp=datetime.datetime.now(),
            algorithm=AlgorithmReference(
                name=self.algorithm_config_response.name,
                key=self.algorithm_config_response.key,
            ),
            terminal=terminal,
        )

    def run(self, detections: list[Detection]) -> list[Detection]:
        detections_to_return: list[Detection] = []
        for detection in detections:
            detection_with_classification = detection.copy(deep=True)
            detection_with_classification.classifications = [self._make_constant_prediction(terminal=True)]
            detections_to_return.append(detection_with_classification)
        return detections_to_return

    algorithm_config_response = AlgorithmConfigResponse(
        name="Constant classifier",
        key="constant-classifier",
        task_type="classification",
        description="Always return a classification of 'Moth'",
        version=1,
        version_name="v1",
        uri="https://huggingface.co/RolnickLab/constant-classifier",
        category_map=AlgorithmCategoryMapResponse(
            data=[
                {
                    "index": 0,
                    "gbif_key": "1234",
                    "label": "Moth",
                    "source": "manual",
                    "taxon_rank": "SUPERFAMILY",
                }
            ],
            labels=["Moth"],
            version="v1",
            description="A classifier that always returns 'Moth'",
            uri="https://huggingface.co/RolnickLab/constant-classifier",
        ),
    )
