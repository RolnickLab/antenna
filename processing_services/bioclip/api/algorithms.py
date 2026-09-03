import datetime
import json
import logging
import math
import os
import random

import torch

from .schemas import (
    AlgorithmCategoryMapResponse,
    AlgorithmConfigResponse,
    AlgorithmTrainingConfig,
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

    def _build_categories(self, classes, label_map) -> list[dict]:
        """
        Map each head row to an Antenna category.

        The label map is keyed by the class value, which is the iNat taxon id for the
        Newfoundland head.
        """
        return [
            {
                "index": index,
                "label": label_map[str(source_class)]["species_name"],
                "taxon_rank": "SPECIES",
                "source_class": str(source_class),
                "inat_taxon_id": label_map[str(source_class)]["inat_taxon_id"],
            }
            for index, source_class in enumerate(classes)
        ]

    def get_category_map(self) -> AlgorithmCategoryMapResponse:
        return AlgorithmCategoryMapResponse(
            data=[],
            labels=[],
            version="v1",
            description="A model without labels.",
            uri=None,
        )

    def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
        return AlgorithmConfigResponse(
            name="Base Algorithm",
            key="base",
            task_type="base",
            description="A base class for all algorithms.",
            version=1,
            version_name="v1",
            category_map=self.get_category_map(),
        )

    def __init__(self):
        self.algorithm_config_response = self.get_algorithm_config_response()


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

    def get_category_map(self) -> AlgorithmCategoryMapResponse:
        return AlgorithmCategoryMapResponse(
            data=[{"index": i, "label": label} for i, label in enumerate(self.candidate_labels)],
            labels=self.candidate_labels,
            version="v1",
            description="Candidate labels used for zero-shot object detection.",
            uri=None,
        )

    def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
        return AlgorithmConfigResponse(
            name="Zero Shot Object Detector",
            key="zero-shot-object-detector",
            task_type="detection",
            description=(
                "Huggingface Zero Shot Object Detection model."
                "Produces both a bounding box and a candidate label classification for each detection."
            ),
            version=1,
            version_name="v1",
            category_map=self.get_category_map(),
        )


class HFImageClassifier(Algorithm):
    """
    A  local classifier that uses the Hugging Face pipeline to classify images.
    """

    model_name: str = "google/vit-base-patch16-224"  # Vision Transformer model trained on ImageNet-1k

    def compile(self):
        saved_models_key = "hf_image_classifier"  # generate a key for each uniquely compiled algorithm

        if saved_models_key not in SAVED_MODELS:
            from transformers import pipeline

            logger.info(f"Compiling {self.algorithm_config_response.name} from scratch...")
            self.model = pipeline("image-classification", model=self.model_name, device=get_best_device())
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

    def get_category_map(self) -> AlgorithmCategoryMapResponse:
        """
        Extract the category map from the model.
        Returns an AlgorithmCategoryMapResponse with labels, data, and model information.
        """
        from transformers.models.auto.configuration_auto import AutoConfig

        logger.info(f"Loading configuration for {self.model_name}")
        config = AutoConfig.from_pretrained(self.model_name)

        # Extract label information
        if not hasattr(config, "id2label") or not config.id2label:
            raise ValueError(
                f"Cannot create category map for model {self.model_name}, no id2label mapping found in config"
            )
        else:
            # Sort labels by index
            # Ensure keys are strings for consistent access
            id2label: dict[str, str] = {str(k): v for k, v in config.id2label.items()}
            indices = sorted([int(k) for k in id2label.keys()])

            # Create labels and data
            labels = [id2label[str(i)] for i in indices]
            data = [{"label": label, "index": idx} for idx, label in zip(indices, labels)]

        # Build description
        description_text = (
            f"Vision Transformer model trained on ImageNet-1k. "
            f"Contains {len(labels)} object classes. Model: {self.model_name}"
        )

        return AlgorithmCategoryMapResponse(
            data=data,
            labels=labels,
            version="ImageNet-1k",
            description=description_text,
            uri=f"https://huggingface.co/{self.model_name}",
        )

    def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
        return AlgorithmConfigResponse(
            name="HF Image Classifier",
            key="hf-image-classifier",
            task_type="classification",
            description="HF ViT for image classification.",
            version=1,
            version_name="v1",
            category_map=self.get_category_map(),
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


class BioCLIPWithLinearHead(torch.nn.Module):
    """
    A frozen BioCLIP image encoder with a linear classification head on top.

    Keeps the encoder, the head and the image transform in a single module so that the
    whole classifier can be cached in SAVED_MODELS as one object.
    """

    def __init__(self, encoder, head, preprocess):
        super().__init__()
        self.encoder = encoder
        self.head = head
        self.preprocess = preprocess

    def forward(self, images: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Returns (logits, features). The features are what the head consumes, so they
        are the right thing to store for retraining a head later."""
        features = self.encoder.encode_image(images).float()
        # The head was fit on L2-normalised embeddings, so normalise here too.
        features = features / features.norm(dim=-1, keepdim=True)
        return self.head(features), features


class BioCLIP25LogRegClassifier(Algorithm):
    """
    A local classifier that uses a frozen BioCLIP 2.5 image encoder with a linear
    logistic-regression head.

    The head is a single Linear layer whose weights come from an sklearn
    LogisticRegression fit on L2-normalised BioCLIP embeddings, so softmax over the
    linear output reproduces sklearn's multinomial predict_proba exactly. See
    scripts/export_logreg_head.py for the conversion.
    """

    model_name: str = "hf-hub:imageomics/bioclip-2.5-vith14"  # BioCLIP 2.5 ViT-H/14, loaded by open_clip
    # The head and its label map are read from the Hugging Face repo that already serves
    # them to the Newfoundland trap classifier demo, so there is a single source of truth
    # for the weights rather than a second copy that can drift.
    head_repo_id: str = "mohammedelabbas/newfoundland-leps-trap-classifier"
    head_repo_type: str = "space"
    head_filename: str = "logreg_head_antenna.npz"
    categories_filename: str = "label_map.json"
    # Read the head from this directory instead of the hub, for offline or local testing.
    # The directory must contain the same two filenames.
    head_local_dir: str | None = os.environ.get("BIOCLIP_HEAD_DIR") or None
    # One cache slot per head. Two heads sharing a slot would silently serve the wrong
    # weights, because the encoder is identical and only the Linear layer differs.
    saved_models_key: str = "bioclip_25_logreg_nf749"
    # Antenna's schema allows omitting the label list per classification when the class
    # list is large. The full list always travels in the category map instead.
    max_labels_in_response: int = 100

    @property
    def head_uri(self) -> str:
        prefix = "spaces/" if self.head_repo_type == "space" else ""
        return f"https://huggingface.co/{prefix}{self.head_repo_id}"

    def _head_file(self, filename: str) -> str:
        if self.head_local_dir:
            logger.info(f"Loading {filename} from local directory {self.head_local_dir}")
            return f"{self.head_local_dir}/{filename}"

        from huggingface_hub import hf_hub_download

        logger.info(f"Loading {filename} from {self.head_repo_id} ({self.head_repo_type})")
        return hf_hub_download(repo_id=self.head_repo_id, filename=filename, repo_type=self.head_repo_type)

    def _load_head_arrays(self):
        """
        Load the exported sklearn LogisticRegression as (weight, bias, classes).

        `classes` holds the label-map key for each row of the weight matrix, so the row
        order of the head and the order of the category map stay tied together.
        """
        import numpy as np

        checkpoint = np.load(self._head_file(self.head_filename))
        return checkpoint["W"], checkpoint["b"], checkpoint["classes"]

    def _load_head(self, embed_dim: int) -> torch.nn.Module:
        weight, bias, _classes = self._load_head_arrays()

        if weight.shape[1] != embed_dim:
            raise ValueError(
                f"Head was fit on {weight.shape[1]}-dim embeddings but {self.model_name} "
                f"produces {embed_dim}-dim embeddings."
            )

        head = torch.nn.Linear(embed_dim, weight.shape[0])
        head.weight.data = torch.from_numpy(weight).float()
        head.bias.data = torch.from_numpy(bias).float()
        return head

    def compile(self):
        saved_models_key = self.saved_models_key

        self.device = get_best_device()
        if saved_models_key not in SAVED_MODELS:
            import open_clip

            logger.info(f"Compiling {self.algorithm_config_response.name} from scratch...")
            encoder, _, preprocess = open_clip.create_model_and_transforms(self.model_name)
            head = self._load_head(encoder.visual.output_dim)
            self.model = BioCLIPWithLinearHead(encoder, head, preprocess).eval().to(self.device)
            SAVED_MODELS[saved_models_key] = self.model
        else:
            logger.info(f"Using saved model for {self.algorithm_config_response.name}...")
            self.model = SAVED_MODELS[saved_models_key]

    def run(self, detections: list[Detection]) -> list[Detection]:
        detections_to_return: list[Detection] = []
        start_time = datetime.datetime.now()

        opened_cropped_images = [detection._pil for detection in detections]  # type: ignore

        # Process the entire batch of cropped images at once
        crops = torch.stack([self.model.preprocess(image.convert("RGB")) for image in opened_cropped_images])
        with torch.inference_mode():
            batch_logits, batch_features = self.model(crops.to(self.device))
            batch_scores = torch.nn.functional.softmax(batch_logits, dim=-1)

        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        assert self.algorithm_config_response.category_map is not None
        category_labels = self.algorithm_config_response.category_map.labels

        for detection, logits, scores, features in zip(
            detections, batch_logits.cpu(), batch_scores.cpu(), batch_features.cpu()
        ):
            classification = category_labels[int(scores.argmax())]
            logger.info(f"Classification: {classification}")

            existing_classifications = detection.classifications

            detection_with_classification = detection.copy(deep=True)
            detection_with_classification.classifications = existing_classifications + [
                ClassificationResponse(
                    classification=classification,
                    labels=category_labels if len(category_labels) <= self.max_labels_in_response else None,
                    scores=scores.tolist(),
                    logits=logits.tolist(),
                    features=features.tolist(),
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

    def get_category_map(self) -> AlgorithmCategoryMapResponse:
        """
        Load the category map exported alongside the head.
        Returns an AlgorithmCategoryMapResponse with labels, data, and model information.
        """
        categories_path = self._head_file(self.categories_filename)
        with open(categories_path) as f:
            label_map = json.load(f)

        if not label_map:
            raise ValueError(
                f"Cannot create category map for model {self.model_name}, "
                f"no categories found in {self.categories_filename}"
            )

        # Row i of the head predicts classes[i], so walk the classes in row order to keep
        # the head and the labels aligned.
        _weight, _bias, classes = self._load_head_arrays()
        categories = self._build_categories(classes, label_map)
        labels = [category["label"] for category in categories]

        # Build description
        description_text = (
            f"Logistic-regression head over frozen {self.model_name} embeddings. "
            f"Contains {len(labels)} classes."
        )

        return AlgorithmCategoryMapResponse(
            data=categories,
            labels=labels,
            version="v1",
            description=description_text,
            uri=self.head_uri,
        )

    def training_config(self) -> AlgorithmTrainingConfig:
        """
        Defaults for retraining this head. Antenna seeds its own copy once, so changing
        these afterwards only affects algorithms registered from here on.
        """
        return AlgorithmTrainingConfig(
            # A linear head matches what is deployed, so a retrained one is a drop-in.
            # An MLP-1 head scores far better on rare species and is the likely next default.
            head_type="linear",
            epochs=300,
            learning_rate=0.01,
            min_per_species=2,
        )

    def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
        return AlgorithmConfigResponse(
            name="BioCLIP 2.5 + LogReg head (Newfoundland, 749 species)",
            key="bioclip-2-5-vith14-logreg-nf749",
            task_type="classification",
            description="Frozen BioCLIP 2.5 (ViT-H/14) encoder with a linear logistic-regression head.",
            # A different head means a different key, not a new version. Antenna looks
            # algorithms up with get_or_create(key=..., version=...) but has a unique
            # constraint on key alone, so bumping the version of an existing key raises
            # an IntegrityError instead of registering the new category map.
            version=1,
            version_name="v1",
            uri=self.head_uri,
            # The encoder is frozen, so only this linear head is retrained. The zero-shot
            # detector in stage 0 is not trainable and stays False.
            trainable=True,
            training_config=self.training_config(),
            category_map=self.get_category_map(),
        )


class BioCLIPPanamaLogRegClassifier(BioCLIP25LogRegClassifier):
    """
    The Panama (BCI + Mount Totumas) head over the same frozen BioCLIP 2.5 encoder.

    Same architecture as the Newfoundland head, but the export carries its label
    vocabulary inside the npz instead of a separate label map, and the vocabulary is
    larger than the number of trained rows: 1,095 names, 900 output classes. The 195
    species with no training data can never be predicted, so they are not categories.
    """

    head_repo_id: str | None = None  # not published; read from a local directory
    head_filename: str = "head_combined.npz"
    categories_filename: str | None = None  # labels travel inside the npz
    head_local_dir: str | None = os.environ.get("BIOCLIP_PANAMA_HEAD_DIR") or None
    saved_models_key: str = "bioclip_25_logreg_panama900"

    @property
    def head_uri(self) -> str | None:
        return None

    def _load_label_vocabulary(self):
        import numpy as np

        return np.load(self._head_file(self.head_filename), allow_pickle=True)["labels"]

    def _build_categories(self, classes, label_map) -> list[dict]:
        # `label_map` is the vocabulary array here, indexed by class value rather than
        # keyed by it.
        return [
            {
                "index": index,
                "label": str(label_map[int(source_class)]),
                "taxon_rank": "SPECIES",
                "source_class": str(int(source_class)),
            }
            for index, source_class in enumerate(classes)
        ]

    def get_category_map(self) -> AlgorithmCategoryMapResponse:
        _weight, _bias, classes = self._load_head_arrays()
        vocabulary = self._load_label_vocabulary()
        categories = self._build_categories(classes, vocabulary)
        labels = [category["label"] for category in categories]

        return AlgorithmCategoryMapResponse(
            data=categories,
            labels=labels,
            version="v1",
            description=(
                f"Logistic-regression head over frozen {self.model_name} embeddings. "
                f"Contains {len(labels)} classes from a {len(vocabulary)}-species vocabulary."
            ),
            uri=self.head_uri,
        )

    def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
        return AlgorithmConfigResponse(
            name="BioCLIP 2.5 + LogReg head (Panama, 900 species)",
            key="bioclip-2-5-vith14-logreg-panama900",
            task_type="classification",
            description="Frozen BioCLIP 2.5 (ViT-H/14) encoder with a linear logistic-regression head.",
            version=1,
            version_name="v1",
            uri=self.head_uri,
            trainable=True,
            training_config=self.training_config(),
            category_map=self.get_category_map(),
        )
