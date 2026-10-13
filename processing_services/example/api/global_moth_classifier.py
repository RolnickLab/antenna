"""
Global moth species classifier for the example processing service.

Adapted from the classifier of the same name in the AMI data companion (trapdata), without its database or queue
dependencies. It classifies cropped detections into ~29k species and returns the raw logits for every class; the
caller derives probabilities from them.
"""

import datetime
import logging
import os
import time

import requests
import torch
import torchvision.transforms

from .algorithms import SAVED_MODELS, Algorithm
from .base import TimmResNet50Base, imagenet_normalization
from .schemas import (
    AlgorithmCategoryMapResponse,
    AlgorithmConfigResponse,
    AlgorithmReference,
    ClassificationResponse,
    Detection,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Public object store holding the model weights and category maps. Override with the MODEL_BASE_URL environment
# variable to use a mirror or a local directory laid out the same way.
DEFAULT_MODEL_BASE_URL = (
    "https://object-arbutus.alliancecan.ca/swift/v1/AUTH_3c987b8fc90743469d42899b1fdb48eb/ami-models/"
)
MODEL_BASE_URL_ENV_VAR = "MODEL_BASE_URL"

WEIGHTS_RELATIVE_PATH = "moths/classification/global_resnet50_20240828_b06d3b3a.pth"
LABELS_RELATIVE_PATH = "moths/classification/global_category_map_with_names_20240828.json"

# Decimal places kept for each logit. The model has ~29k classes, so every digit multiplies the response size.
LOGIT_DECIMALS = 4

# Category maps by labels path, so repeated `/info` calls do not re-read and re-parse the labels file.
_CATEGORY_MAPS: dict[str, dict[int, str]] = {}


def get_model_url(relative_path: str) -> str:
    """Join a model file path onto MODEL_BASE_URL (or the default public store)."""
    base_url = os.environ.get(MODEL_BASE_URL_ENV_VAR) or DEFAULT_MODEL_BASE_URL
    return f"{base_url.rstrip('/')}/{relative_path}"


class GlobalMothClassifier(Algorithm, TimmResNet50Base):
    """
    Classifies cropped detections into one of the species in the global category map.

    `Algorithm` provides the interface the pipelines use, and `TimmResNet50Base` loads the weights and labels. The
    weights are only downloaded when `compile()` runs, so creating the object and describing it in `/info` is cheap.
    The loaded model is shared between instances, so later requests do not reload it.
    """

    name = "Global Species Classifier - Aug 2024"
    description = (
        "Trained on August 28th, 2024 for 29,176 species. "
        "https://wandb.ai/moth-ai/global-moth-classifier/runs/h0cuqrbc/overview"
    )

    input_size = 128
    normalization = imagenet_normalization
    default_taxon_rank = "SPECIES"
    batch_size = 4

    def __init__(self, **kwargs):
        self._init_kwargs = {
            "weights_path": get_model_url(WEIGHTS_RELATIVE_PATH),
            "labels_path": get_model_url(LABELS_RELATIVE_PATH),
            **kwargs,
        }
        self.weights_path = self._init_kwargs["weights_path"]
        self.labels_path = self._init_kwargs["labels_path"]
        self.model = None
        self.transforms = None
        self.category_map = {}
        self.num_classes = None
        self._algorithm_config_response: AlgorithmConfigResponse | None = None

    @property
    def algorithm_config_response(self) -> AlgorithmConfigResponse:
        """The algorithm description, including the category map once the labels can be loaded."""
        if self._algorithm_config_response is not None:
            return self._algorithm_config_response
        config = self.get_algorithm_config_response()
        # Do not remember a description built without labels, so a later call can retry the download.
        if self.category_map:
            self._algorithm_config_response = config
        return config

    def _saved_model_key(self) -> str:
        return f"{type(self).__name__}:{self.weights_path}:{self.labels_path}:{self._init_kwargs.get('device')}"

    def compile(self):
        """Download (if needed) and load the weights and labels. Reuses an already loaded model."""
        if self.model is not None:
            return

        saved_key = self._saved_model_key()
        if saved_key in SAVED_MODELS:
            logger.info(f"Using saved model for {self.name}")
            self.__dict__.update(SAVED_MODELS[saved_key])
            return

        logger.info(f"Compiling {self.name} from {self.weights_path}")
        TimmResNet50Base.__init__(self, **self._init_kwargs)
        SAVED_MODELS[saved_key] = {
            name: getattr(self, name)
            for name in ("model", "transforms", "category_map", "num_classes", "weights", "device")
        }
        logger.info(f"Compiled {self.name}: {self.num_classes} classes on {self.device}")

    def get_transforms(self) -> torchvision.transforms.Compose:
        return torchvision.transforms.Compose(
            [
                torchvision.transforms.Resize((self.input_size, self.input_size)),
                torchvision.transforms.ToTensor(),
                self.normalization,
            ]
        )

    def post_process_batch(self, logits: torch.Tensor) -> list[dict]:
        """Return the logits for every class, rounded to keep the response small. Probabilities are not computed."""
        return [{"logits": [round(value, LOGIT_DECIMALS) for value in row.tolist()]} for row in logits.cpu()]

    def run(self, detections: list[Detection]) -> list[Detection]:
        """
        Classify detections from their cropped images.

        Detections without a cropped image are skipped with a warning and are not returned.
        """
        if not detections:
            return []
        if self.model is None or self.transforms is None:
            raise RuntimeError("Model not compiled. Call compile() first.")

        logger.info(f"Running {self.name} on {len(detections)} detections")
        classified_detections: list[Detection] = []

        for i in range(0, len(detections), self.batch_size):
            # Only detections that have an image are batched; predictions are paired with this list, not the input.
            batched_detections: list[Detection] = []
            batch_images = []
            for detection in detections[i : i + self.batch_size]:
                if detection._pil is None:
                    logger.warning(f"Detection {detection.id} has no cropped image, skipping it")
                    continue
                batched_detections.append(detection)
                batch_images.append(detection._pil.convert("RGB"))

            if not batched_detections:
                continue

            batch_tensor = torch.stack([self.transforms(image) for image in batch_images])
            start_time = time.perf_counter()
            predictions = self.post_process_batch(self.predict_batch(batch_tensor))
            inference_time = (time.perf_counter() - start_time) / len(batched_detections)

            for detection, prediction in zip(batched_detections, predictions, strict=True):
                logits = prediction["logits"]
                best_index = max(range(len(logits)), key=logits.__getitem__)
                classification = ClassificationResponse(
                    classification=self.category_map[best_index],
                    logits=logits,
                    inference_time=inference_time,
                    timestamp=datetime.datetime.now(),
                    algorithm=AlgorithmReference(name=self.name, key=self.get_key()),
                    terminal=True,
                )
                classified_detections.append(detection.model_copy(update={"classifications": [classification]}))

        logger.info(f"Classified {len(classified_detections)} of {len(detections)} detections")
        return classified_detections

    def get_category_map(self) -> AlgorithmCategoryMapResponse:
        if not self.category_map and self.labels_path in _CATEGORY_MAPS:
            self.category_map = _CATEGORY_MAPS[self.labels_path]
        if not self.category_map:
            try:
                self.category_map = self.get_labels(self.labels_path)
                _CATEGORY_MAPS[self.labels_path] = self.category_map
            except (requests.RequestException, OSError, ValueError) as error:
                logger.warning(f"Could not load the category labels from {self.labels_path}: {error}")

        data = [
            {"index": index, "label": label, "taxon_rank": self.default_taxon_rank}
            for index, label in sorted(self.category_map.items())
        ]
        return AlgorithmCategoryMapResponse(
            data=data,
            labels=[row["label"] for row in data],
            version="v1",
            description=f"Global moth species classifier with {len(data)} species",
            uri=self.labels_path,
        )

    def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
        return AlgorithmConfigResponse(
            name=self.name,
            key=self.get_key(),
            task_type="classification",
            description=self.description,
            version=1,
            version_name="v1",
            category_map=self.get_category_map(),
            uri=self.weights_path,
        )
