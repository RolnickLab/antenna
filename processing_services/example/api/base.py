"""
Simplified base classes for inference models without database dependencies.
Adapted from trapdata.ml.models.base but streamlined for processing service use.
"""

import json
import logging
from typing import Any

import torch
import torchvision.transforms

from .utils import get_best_device, get_or_download_file

logger = logging.getLogger(__name__)


# Standard normalization transforms
imagenet_normalization = torchvision.transforms.Normalize(
    mean=[0.485, 0.456, 0.406],  # RGB
    std=[0.229, 0.224, 0.225],  # RGB
)

tensorflow_normalization = torchvision.transforms.Normalize(
    mean=[0.5, 0.5, 0.5],  # RGB
    std=[0.5, 0.5, 0.5],  # RGB
)


class SimplifiedInferenceBase:
    """
    Simplified base class for inference models without database or queue dependencies.
    """

    name: str = "Unknown Inference Model"
    description: str = ""
    weights_path: str | None = None
    labels_path: str | None = None
    category_map: dict[int, str] = {}
    num_classes: int | None = None
    default_taxon_rank: str = "SPECIES"
    normalization = tensorflow_normalization
    batch_size: int = 4
    device: str | None = None

    def __init__(self, **kwargs):
        # Override any class attributes with provided kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)

        logger.info(f"Initializing simplified inference class {self.name}")

        self.device = self.device or get_best_device()
        self.category_map = self.get_labels(self.labels_path)
        self.num_classes = self.num_classes or len(self.category_map)
        self.weights = self.get_weights(self.weights_path)
        self.transforms = self.get_transforms()

        logger.info(f"Loading model for {self.name} with {len(self.category_map or [])} categories")
        self.model = self.get_model()

    @classmethod
    def get_key(cls) -> str:
        """Generate a unique key for this algorithm."""
        if hasattr(cls, "key") and cls.key:
            return cls.key
        else:
            return cls.name.lower().replace(" ", "-").replace("/", "-")

    def get_weights(self, weights_path: str | None) -> str | None:
        """Download and cache model weights."""
        if weights_path:
            logger.info(f"⬇️  Downloading model weights from: {weights_path}")
            weights_file = str(get_or_download_file(weights_path, tempdir_prefix="models"))
            logger.info(f"✅ Model weights downloaded to: {weights_file}")
            return weights_file
        else:
            logger.warning(f"No weights specified for model {self.name}")
            return None

    def get_labels(self, labels_path: str | None) -> dict[int, str]:
        """Download and load category labels."""
        if not labels_path:
            return {}

        logger.info(f"⬇️  Downloading category labels from: {labels_path}")
        local_path = get_or_download_file(labels_path, tempdir_prefix="models")
        logger.info(f"📝 Loading category labels from: {local_path}")

        with open(local_path) as f:
            labels = json.load(f)

        # Convert label->index mapping to index->label mapping
        index_to_label = {index: label for label, index in labels.items()}
        logger.info(f"✅ Loaded {len(index_to_label)} category labels")
        return index_to_label

    def get_transforms(self) -> torchvision.transforms.Compose:
        """Get image preprocessing transforms."""
        return torchvision.transforms.Compose(
            [
                torchvision.transforms.Resize((224, 224)),
                torchvision.transforms.ToTensor(),
                self.normalization,
            ]
        )

    def get_model(self) -> torch.nn.Module:
        """
        Load and return the PyTorch model.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement get_model()")

    def predict_batch(self, batch: torch.Tensor) -> torch.Tensor:
        """
        Run inference on a batch of images.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement predict_batch()")

    def post_process_batch(self, logits: torch.Tensor) -> Any:
        """
        Post-process model outputs.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement post_process_batch()")


class ResNet50Base(SimplifiedInferenceBase):
    """
    Base class for ResNet50-based models.
    """

    input_size: int = 224
    normalization = imagenet_normalization

    def get_transforms(self) -> torchvision.transforms.Compose:
        """Get ResNet50-specific transforms."""
        return torchvision.transforms.Compose(
            [
                torchvision.transforms.Resize((self.input_size, self.input_size)),
                torchvision.transforms.ToTensor(),
                self.normalization,
            ]
        )

    def get_model(self) -> torch.nn.Module:
        """Load ResNet50 model with custom classifier."""
        import torchvision.models as models

        logger.info("🏗️  Creating ResNet50 model architecture...")
        # Create ResNet50 backbone
        model = models.resnet50(weights=None)

        # Replace final classifier layer
        if self.num_classes is None:
            raise ValueError("num_classes must be set before loading model")
        logger.info(f"🔧 Setting up classifier layer for {self.num_classes} classes...")
        model.fc = torch.nn.Linear(model.fc.in_features, self.num_classes)

        # Load pretrained weights
        if self.weights:
            logger.info(f"📂 Loading pretrained weights from: {self.weights}")
            checkpoint = torch.load(self.weights, map_location=self.device)

            # Handle different checkpoint formats
            if "model_state_dict" in checkpoint:
                logger.info("📥 Loading state dict from 'model_state_dict' key...")
                model.load_state_dict(checkpoint["model_state_dict"])
            elif "state_dict" in checkpoint:
                logger.info("📥 Loading state dict from 'state_dict' key...")
                model.load_state_dict(checkpoint["state_dict"])
            else:
                logger.info("📥 Loading state dict directly...")
                model.load_state_dict(checkpoint)
            logger.info("✅ Model weights loaded successfully!")
        else:
            logger.warning("⚠️  No pretrained weights provided - using random initialization")

        logger.info(f"📱 Moving model to device: {self.device}")
        model = model.to(self.device)
        model.eval()
        logger.info("✅ Model ready for inference!")
        return model

    def predict_batch(self, batch: torch.Tensor) -> torch.Tensor:
        """Run inference on batch."""
        with torch.no_grad():
            batch = batch.to(self.device)
            outputs = self.model(batch)
            return outputs

    def post_process_batch(self, logits: torch.Tensor) -> list:
        """Convert logits to predictions."""
        probabilities = torch.softmax(logits, dim=1)
        predictions = []

        for prob_tensor in probabilities:
            prob_list = prob_tensor.cpu().numpy().tolist()
            predictions.append(
                {
                    "scores": prob_list,
                    "logits": logits[len(predictions)].cpu().numpy().tolist(),
                }
            )

        return predictions


class TimmResNet50Base(ResNet50Base):
    """
    Base class for timm ResNet50-based models.
    """

    def get_model(self) -> torch.nn.Module:
        """Load timm ResNet50 model."""
        import timm

        # Create timm ResNet50 model
        model = timm.create_model("resnet50", pretrained=False, num_classes=self.num_classes)

        # Load pretrained weights
        if self.weights:
            checkpoint = torch.load(self.weights, map_location=self.device)

            # Handle different checkpoint formats
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            elif "state_dict" in checkpoint:
                model.load_state_dict(checkpoint["state_dict"])
            else:
                model.load_state_dict(checkpoint)

        model = model.to(self.device)
        model.eval()
        return model
