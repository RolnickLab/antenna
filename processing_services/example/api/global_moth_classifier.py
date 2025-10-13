"""
Global Moth Classifier algorithm implementation.
Simplified version of trapdata.api.models.classification.MothClassifierGlobal
adapted for the processing service framework.
"""

import datetime
import logging

import torch
import torchvision.transforms

from .algorithms import Algorithm
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


class GlobalMothClassifier(Algorithm, TimmResNet50Base):
    """
    Global Moth Species Classifier.

    Simplified version of the trapdata GlobalMothSpeciesClassifier
    that works without database dependencies.
    """

    name = "Global Species Classifier - Aug 2024"
    description = (
        "Trained on August 28th, 2024 for 29,176 species. "
        "https://wandb.ai/moth-ai/global-moth-classifier/runs/h0cuqrbc/overview"
    )
    weights_path = (
        "https://object-arbutus.cloud.computecanada.ca/ami-models/moths/classification/"
        "global_resnet50_20240828_b06d3b3a.pth"
    )
    labels_path = (
        "https://object-arbutus.cloud.computecanada.ca/ami-models/moths/classification/"
        "global_category_map_with_names_20240828.json"
    )

    # Model configuration
    input_size = 128
    normalization = imagenet_normalization
    default_taxon_rank = "SPECIES"
    batch_size = 4

    def __init__(self, **kwargs):
        """Initialize the global moth classifier."""
        # Initialize Algorithm parent class
        Algorithm.__init__(self)

        # Store kwargs for later use in compile()
        self._init_kwargs = kwargs

        # Initialize basic attributes without loading model
        self.model = None
        self.transforms = None
        self.category_map = {}  # Empty dict for now
        self.num_classes = 29176  # Known number of classes

        logger.info(f"Initialized {self.name} (model loading deferred to compile())")

    @property
    def algorithm_config_response(self) -> AlgorithmConfigResponse:
        """Get algorithm configuration for API response."""
        if not hasattr(self, "_algorithm_config_response"):
            # Create a basic config response before compilation
            self._algorithm_config_response = AlgorithmConfigResponse(
                name=self.name,
                key=self.get_key(),
                task_type="classification",
                description=self.description,
                version=1,
                version_name="v1",
                category_map=AlgorithmCategoryMapResponse(
                    data=[],
                    labels=[],
                    version="v1",
                    description="Global moth species classifier (not yet compiled)",
                    uri=self.labels_path,
                ),
                uri=self.weights_path,
            )
        return self._algorithm_config_response

    @algorithm_config_response.setter
    def algorithm_config_response(self, value: AlgorithmConfigResponse):
        """Set algorithm configuration response."""
        self._algorithm_config_response = value

    def compile(self):
        """Load model weights and initialize transforms (called by pipeline)."""
        if self.model is not None:
            logger.info("Model already compiled, skipping...")
            return

        logger.info(f"🔧 Compiling {self.name}...")
        logger.info(f"   📊 Expected classes: {self.num_classes}")
        logger.info(f"   🏷️  Labels URL: {self.labels_path}")
        logger.info(f"   ⚖️  Weights URL: {self.weights_path}")

        # Initialize the TimmResNet50Base now (this will download weights/labels)
        logger.info("   📥 Downloading model weights and labels...")
        TimmResNet50Base.__init__(self, **self._init_kwargs)

        # Set algorithm config response
        logger.info("   📋 Setting up algorithm configuration...")
        self.algorithm_config_response = self.get_algorithm_config_response()

        logger.info(f"✅ {self.name} compiled successfully!")
        logger.info(f"   📊 Loaded {len(self.category_map)} species categories")
        logger.info(f"   🔧 Model device: {getattr(self, 'device', 'unknown')}")
        logger.info(f"   🖼️  Input size: {self.input_size}x{self.input_size}")

    def get_transforms(self) -> torchvision.transforms.Compose:
        """Get transforms specific to this model."""
        return torchvision.transforms.Compose(
            [
                torchvision.transforms.Resize((self.input_size, self.input_size)),
                torchvision.transforms.ToTensor(),
                self.normalization,
            ]
        )

    def run(self, detections: list[Detection]) -> list[Detection]:
        """
        Run classification on a list of detections.

        Args:
            detections: List of Detection objects with cropped images

        Returns:
            List of Detection objects with added classifications
        """
        if not detections:
            return []

        # Ensure model is compiled
        if self.model is None:
            raise RuntimeError("Model not compiled. Call compile() first.")

        logger.info(f"Running {self.name} on {len(detections)} detections")

        # Process detections in batches
        classified_detections = []

        for i in range(0, len(detections), self.batch_size):
            batch_detections = detections[i : i + self.batch_size]
            batch_images = []

            # Prepare batch of images
            for detection in batch_detections:
                if detection._pil:
                    # Convert to RGB if needed
                    if detection._pil.mode != "RGB":
                        img = detection._pil.convert("RGB")
                    else:
                        img = detection._pil
                    batch_images.append(img)
                else:
                    logger.warning(f"Detection {detection.id} has no PIL image")
                    continue

            if not batch_images:
                continue

            # Transform images
            if self.transforms is None:
                raise RuntimeError("Transforms not initialized. Call compile() first.")
            batch_tensor = torch.stack([self.transforms(img) for img in batch_images])

            # Run inference
            start_time = datetime.datetime.now()
            predictions = self.predict_batch(batch_tensor)
            processed_predictions = self.post_process_batch(predictions)
            end_time = datetime.datetime.now()

            inference_time = (end_time - start_time).total_seconds() / len(batch_images)

            # Add classifications to detections
            for detection, prediction in zip(batch_detections, processed_predictions):
                # Get best prediction
                best_score = max(prediction["scores"])
                best_idx = prediction["scores"].index(best_score)
                best_label = self.category_map.get(best_idx, f"class_{best_idx}")

                classification = ClassificationResponse(
                    classification=best_label,
                    labels=[best_label],
                    scores=[best_score],
                    logits=prediction["logits"],
                    inference_time=inference_time,
                    timestamp=datetime.datetime.now(),
                    algorithm=AlgorithmReference(
                        name=self.name,
                        key=self.get_key(),
                    ),
                    terminal=True,
                )

                # Add classification to detection
                detection_with_classification = detection.copy(deep=True)
                detection_with_classification.classifications = [classification]
                classified_detections.append(detection_with_classification)

        logger.info(f"Classified {len(classified_detections)} detections")
        return classified_detections

    def get_category_map(self) -> AlgorithmCategoryMapResponse:
        """Get category map for API response."""
        categories_sorted_by_index = sorted(self.category_map.items(), key=lambda x: x[0])
        categories_data = [
            {
                "index": index,
                "label": label,
                "taxon_rank": self.default_taxon_rank,
            }
            for index, label in categories_sorted_by_index
        ]
        label_strings = [cat["label"] for cat in categories_data]

        return AlgorithmCategoryMapResponse(
            data=categories_data,
            labels=label_strings,
            version="v1",
            description=f"Global moth species classifier with {len(categories_data)} species",
            uri=self.labels_path,
        )

    def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
        """Get algorithm configuration for API response."""
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
