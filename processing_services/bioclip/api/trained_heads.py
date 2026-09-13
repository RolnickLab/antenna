"""
Serve the heads this service has retrained, alongside the one it shipped with.

A retrained head is useless if nothing can select it. Each one saved to disk is offered as
its own algorithm and its own pipeline, so Antenna sees it in /info and a user can pick it
the same way they pick any other. The original head stays exactly where it was: a retrain
adds a choice, it never replaces one.
"""

import json
import logging
import os
import pathlib
import typing

logger = logging.getLogger(__name__)

# Where the training endpoint writes heads. Kept off the model cache so a training run
# cannot overwrite the head the service is currently serving.
TRAINED_HEADS_DIR = os.environ.get("BIOCLIP_TRAINED_HEADS_DIR", "/data/bioclip-service/trained_heads")

HEAD_SUFFIX = ".npz"
LABELS_SUFFIX = ".label_map.json"

# Prefix for the algorithm key and pipeline slug of a retrained head. Antenna keys
# algorithms by this string, so changing it orphans everything already registered.
RETRAINED_PREFIX = "bioclip-2-5-retrained"


class TrainedHead(typing.NamedTuple):
    """One head this service has produced, as found on disk."""

    name: str
    head_path: pathlib.Path
    labels_path: pathlib.Path
    metadata: dict

    @property
    def algorithm_key(self) -> str:
        return f"{RETRAINED_PREFIX}-{self.name}"

    @property
    def pipeline_slug(self) -> str:
        return f"{RETRAINED_PREFIX}-{self.name}-pipeline"

    @property
    def labels(self) -> list[str]:
        return [str(label) for label in self.metadata.get("labels", [])]


def discover(directory: str | None = None) -> list[TrainedHead]:
    """
    List the heads saved on disk.

    Reads the label map rather than the weights: this runs at startup and after every
    training run, and the weights are only needed once a head is actually used.
    """
    path = pathlib.Path(directory or TRAINED_HEADS_DIR)
    if not path.is_dir():
        return []

    heads: list[TrainedHead] = []
    for head_path in sorted(path.glob(f"*{HEAD_SUFFIX}")):
        name = head_path.name[: -len(HEAD_SUFFIX)]
        labels_path = path / f"{name}{LABELS_SUFFIX}"
        if not labels_path.exists():
            logger.warning(f"Skipping {head_path.name}: no label map beside it, so its classes are unknown")
            continue
        try:
            metadata = json.loads(labels_path.read_text())
        except (OSError, ValueError) as e:
            logger.warning(f"Skipping {head_path.name}: could not read its label map ({e})")
            continue
        if not metadata.get("labels"):
            logger.warning(f"Skipping {head_path.name}: its label map lists no species")
            continue
        heads.append(TrainedHead(name=name, head_path=head_path, labels_path=labels_path, metadata=metadata))

    logger.info(f"Found {len(heads)} retrained head(s) in {path}")
    return heads


def make_classifier_class(head: TrainedHead):
    """
    Build the algorithm class that serves one retrained head.

    A subclass rather than a separate implementation: the weights have the same shape as
    the head it was trained from, so everything about running it is already written. Only
    where the file lives and what it is called differ.
    """
    from .algorithms import BioCLIP25LogRegClassifier
    from .schemas import AlgorithmCategoryMapResponse, AlgorithmConfigResponse, AlgorithmTrainingInfo

    metrics = head.metadata.get("metrics") or {}
    trained_at = head.metadata.get("trained_at")
    labels = head.labels

    class RetrainedClassifier(BioCLIP25LogRegClassifier):
        head_repo_id = None
        head_local_dir = str(head.head_path.parent)
        head_filename = head.head_path.name
        categories_filename = head.labels_path.name
        saved_models_key = f"retrained_{head.name}"

        @property
        def head_uri(self):
            return None

        def get_category_map(self) -> AlgorithmCategoryMapResponse:
            crops = sum((head.metadata.get("counts") or {}).values())
            return AlgorithmCategoryMapResponse(
                data=[{"index": i, "label": name, "taxon_rank": "SPECIES"} for i, name in enumerate(labels)],
                labels=labels,
                version=head.name,
                description=f"Retrained on {crops} verified crops.",
            )

        def get_algorithm_config_response(self) -> AlgorithmConfigResponse:
            return AlgorithmConfigResponse(
                name=f"BioCLIP 2.5 + LogReg head (retrained {head.name})",
                key=head.algorithm_key,
                task_type="classification",
                description="Retrained from species verified in Antenna.",
                version=1,
                version_name=head.name,
                uri=None,
                trainable=True,
                training_config=self.training_config(),
                training_info=AlgorithmTrainingInfo(
                    trained_at=trained_at,
                    metrics=metrics,
                    dataset_classes=len(labels),
                ),
                category_map=self.get_category_map(),
            )

    RetrainedClassifier.__name__ = f"RetrainedClassifier_{head.name.replace('-', '_')}"
    return RetrainedClassifier


def make_pipeline_class(head: TrainedHead):
    """
    Build the pipeline that runs one retrained head.

    Antenna runs pipelines, not algorithms, so a head with no pipeline cannot be selected.
    Stage 0 is the same detector the original pipeline uses.
    """
    from .algorithms import ZeroShotObjectDetector
    from .pipelines import BioCLIP25LogRegPipeline
    from .schemas import PipelineConfigResponse

    classifier_class = make_classifier_class(head)

    # Filled in here, not in get_stages(): /info reads the class-level config, and
    # get_stages() only runs once a pipeline is actually instantiated to process images.
    # A pipeline advertised with no algorithms registers in Antenna with none attached.
    stage_configs = [
        ZeroShotObjectDetector().algorithm_config_response,
        classifier_class().algorithm_config_response,
    ]

    class RetrainedPipeline(BioCLIP25LogRegPipeline):
        config = PipelineConfigResponse(
            name=f"BioCLIP 2.5 Retrained Head ({head.name})",
            slug=head.pipeline_slug,
            description="Zero shot object detector with a head retrained from verified species.",
            version=1,
            algorithms=stage_configs,
        )

        def get_stages(self):
            detector = ZeroShotObjectDetector()
            if "candidate_labels" in self.request_config:
                detector.candidate_labels = self.request_config["candidate_labels"]
            return [detector, classifier_class()]

    RetrainedPipeline.__name__ = f"RetrainedPipeline_{head.name.replace('-', '_')}"
    return RetrainedPipeline


def register(pipeline_choices: dict, algorithm_choices: dict, directory: str | None = None) -> list[str]:
    """
    Add every head on disk to the service's registries.

    Called at startup and again after training, so a head becomes selectable without a
    restart. Returns the pipeline slugs that were added.
    """
    added: list[str] = []
    for head in discover(directory):
        if head.pipeline_slug in pipeline_choices:
            continue
        try:
            pipeline_class = make_pipeline_class(head)
            classifier = make_classifier_class(head)()
            config = classifier.algorithm_config_response
        except Exception as e:
            logger.error(f"Could not offer retrained head '{head.name}': {e}")
            continue
        pipeline_choices[head.pipeline_slug] = pipeline_class
        algorithm_choices[config.key] = config
        added.append(head.pipeline_slug)

    if added:
        logger.info(f"Offering {len(added)} retrained head(s): {', '.join(added)}")
    return added
