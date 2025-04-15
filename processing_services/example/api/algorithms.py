import datetime
import logging

from .schemas import (
    AlgorithmConfigResponse,
    AlgorithmReference,
    BoundingBox,
    ClassificationResponse,
    Detection,
    SourceImage,
)
from .utils import get_or_download_file

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

SAVED_MODELS = {}


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


class ConstantLocalizer(Algorithm):
    """
    Returns 2 constant bounding boxes for each image.
    """

    def compile(self):
        pass

    def run(self, source_images: list[SourceImage]) -> list[Detection]:
        detector_responses: list[Detection] = []

        for source_image in source_images:
            source_image.open(raise_exception=True)
            start_time = datetime.datetime.now()

            if source_image.width and source_image.height and source_image._pil:
                x1 = source_image.width * 0.1
                x2 = source_image.width * 0.3
                y1 = source_image.height * 0.1
                y2 = source_image.height * 0.3
                end_time = datetime.datetime.now()
                elapsed_time = (end_time - start_time).total_seconds()

                cropped_image_pil = source_image._pil.crop((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
                detection = Detection(
                    id=f"{source_image.id}-crop-{x1}-{y1}-{x2}-{y2}",
                    url=source_image.url,  # @TODO: ideally, should save cropped image at separate url
                    width=cropped_image_pil.width,
                    height=cropped_image_pil.height,
                    timestamp=datetime.datetime.now(),
                    source_image=source_image,
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
                )
                detection._pil = cropped_image_pil
                detector_responses.append(detection)

                start_time = datetime.datetime.now()
                x1 = source_image.width * 0.6
                x2 = source_image.width * 0.8
                y1 = source_image.height * 0.6
                y2 = source_image.height * 0.8
                end_time = datetime.datetime.now()
                elapsed_time = (end_time - start_time).total_seconds()

                cropped_image_pil = source_image._pil.crop((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
                detection = Detection(
                    id=f"{source_image.id}-crop-{x1}-{y1}-{x2}-{y2}",
                    url=source_image.url,  # @TODO: ideally, should save cropped image at separate url
                    width=cropped_image_pil.width,
                    height=cropped_image_pil.height,
                    timestamp=datetime.datetime.now(),
                    source_image=source_image,
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
                )
                detection._pil = cropped_image_pil
                detector_responses.append(detection)
            else:
                raise ValueError(f"Source image {source_image.id} does not have width and height attributes.")

        return detector_responses

    algorithm_config_response = AlgorithmConfigResponse(
        name="Constant Localizer",
        key="constant-localizer",
        task_type="localization",
        description="Returns 2 constant bounding boxes for each image.",
        version=1,
        version_name="v1",
        category_map=None,
    )


class FlatBugLocalizer(Algorithm):
    """
    Darsa Group flat-bug detection and segmentation.
    """

    def compile(self, device="cpu", dtype="float16"):
        saved_models_key = (
            f"flat_bug_localizer_{device}_{dtype}"  # generate a key for each uniquely compiled algorithm
        )

        if saved_models_key not in SAVED_MODELS:
            from flat_bug.predictor import Predictor

            logger.info(f"Compiling {self.algorithm_config_response.name} from scratch...")
            self.model = Predictor(device=device, dtype=dtype)
            SAVED_MODELS[saved_models_key] = self.model
        else:
            logger.info(f"Using saved model for {self.algorithm_config_response.name}...")
            self.model = SAVED_MODELS[saved_models_key]

    def run(self, source_images: list[SourceImage]) -> list[Detection]:
        detector_responses: list[Detection] = []
        for source_image in source_images:
            source_image.open(raise_exception=True)

            if source_image.width and source_image.height and source_image._pil:
                start_time = datetime.datetime.now()
                path = str(get_or_download_file(source_image.url))
                logger.info(f"Predicting {path}")
                prediction = self.model(path)
                logger.info(f"Predicted: {prediction.json_data}")
                logger.info(f"Prediction: {prediction.json_data['boxes']}")
                end_time = datetime.datetime.now()
                elapsed_time = (end_time - start_time).total_seconds()

                bboxes = [
                    BoundingBox(x1=box[0], y1=box[1], x2=box[2], y2=box[3]) for box in prediction.json_data["boxes"]
                ]

                for bbox in bboxes:
                    cropped_image_pil = source_image._pil.crop(
                        (min(bbox.x1, bbox.x2), min(bbox.y1, bbox.y2), max(bbox.x1, bbox.x2), max(bbox.y1, bbox.y2))
                    )
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
                    )
                    detection._pil = cropped_image_pil
                    detector_responses.append(detection)
            else:
                raise ValueError(f"Source image {source_image.id} does not have width and height attributes.")

        return detector_responses

    algorithm_config_response = AlgorithmConfigResponse(
        name="Flat Bug Localizer",
        key="flat-bug-localizer",
        task_type="localization",
        description="Darsa Group flat-bug detection and segmentation.",
        version=1,
        version_name="v1",
        category_map=None,
    )


class ZeroShotObjectDetector(Algorithm):
    """
    Huggingface Zero-Shot Object Detection model.
    """

    candidate_labels: list[str] = ["bug", "moth", "butterfly", "insect"]

    def compile(self):
        saved_models_key = "zero_shot_object_detector"  # generate a key for each uniquely compiled algorithm

        if saved_models_key not in SAVED_MODELS:
            from transformers import pipeline

            logger.info(f"Compiling {self.algorithm_config_response.name} from scratch...")
            checkpoint = "google/owlv2-base-patch16-ensemble"
            self.model = pipeline(model=checkpoint, task="zero-shot-object-detection")
            SAVED_MODELS[saved_models_key] = self.model
        else:
            logger.info(f"Using saved model for {self.algorithm_config_response.name}...")
            self.model = SAVED_MODELS[saved_models_key]

    def run(self, source_images: list[SourceImage]) -> list[Detection]:
        detector_responses: list[Detection] = []
        for source_image in source_images:
            source_image.open(raise_exception=True)

            if source_image.width and source_image.height and source_image._pil:
                start_time = datetime.datetime.now()
                logger.info("Predicting...")
                if not self.candidate_labels:
                    raise ValueError("No candidate labels are provided during inference.")
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
                                terminal=True,
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
        description="Huggingface Zero Shot Object Detection model.",
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
        name="HF Image Classifier",
        key="hf-image-classifier",
        task_type="classification",
        description="HF ViT for image classification.",
        version=1,
        version_name="v1",
        category_map=None,
    )
