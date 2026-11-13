"""Validate and store the feature vectors that processing services return in pipeline results."""

import logging

import numpy as np

from ami.main.models import Detection, SourceImage
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models.algorithm import Algorithm, get_known_algorithm
from ami.ml.models.embedding import EMBEDDING_BATCH_SIZE, DetectionEmbedding
from ami.ml.schemas import DetectionResponse

logger = logging.getLogger(__name__)


# The largest value a half-precision float holds; vectors are stored in half precision.
HALF_PRECISION_MAX = 65504.0


class EmbeddingRefused(PipelineNotConfigured):
    """Raised when a vector in the results cannot be stored, before any of the results are saved."""


def validate_detection_embeddings(
    detection_responses: list[DetectionResponse], algorithms_known: dict[str, Algorithm]
) -> None:
    """Raise ``EmbeddingRefused`` if any vector in these results cannot be stored. Call it before saving anything.

    Each vector must come from an algorithm registered for the pipeline that declares the length of its
    vectors, have that length, and hold only finite values within half precision (±65,504). A detection
    may carry one vector per algorithm, only if it has a bounding box, on a capture that belongs to a project.
    """
    capture_ids = set()
    for detection_resp in detection_responses:
        if not detection_resp.embeddings:
            continue
        if detection_resp.bbox is None:
            raise EmbeddingRefused(
                f"A detection without a bounding box on capture {detection_resp.source_image_id} carries feature "
                "vectors; only detected objects can have them."
            )
        keys = [embedding_resp.algorithm.key for embedding_resp in detection_resp.embeddings]
        if len(keys) != len(set(keys)):
            raise EmbeddingRefused(f"A detection carries more than one vector from one algorithm: {keys}.")
        capture_ids.add(detection_resp.source_image_id)
        for embedding_resp in detection_resp.embeddings:
            algorithm = get_known_algorithm(algorithms_known, embedding_resp.algorithm.key, "Embedding")
            if algorithm.embedding_dimensions is None:
                raise EmbeddingRefused(
                    f"Algorithm {algorithm.key} sent a feature vector but declares no vector length. Its processing "
                    "service must declare embedding_dimensions for it, then register its pipelines again."
                )
            if len(embedding_resp.features) != algorithm.embedding_dimensions:
                raise EmbeddingRefused(
                    f"Algorithm {algorithm.key} is registered with {algorithm.embedding_dimensions}-dimension "
                    f"vectors but sent one of length {len(embedding_resp.features)}."
                )
            values = np.asarray(embedding_resp.features, dtype=np.float64)
            if not (np.isfinite(values).all() and np.abs(values).max() <= HALF_PRECISION_MAX):
                raise EmbeddingRefused(
                    f"Algorithm {algorithm.key} sent a vector with values that are not finite or are beyond "
                    f"±{HALF_PRECISION_MAX:g}, which half precision cannot store."
                )
    without_project = list(
        SourceImage.objects.filter(pk__in=capture_ids, project__isnull=True).values_list("pk", flat=True)
    )
    if without_project:
        raise EmbeddingRefused(
            f"Captures {without_project} belong to no project, so the feature vectors of their detections "
            "cannot be stored."
        )


def create_detection_embeddings(
    saved_detections: list[tuple[Detection, DetectionResponse]],
    algorithms_known: dict[str, Algorithm],
    logger: logging.Logger = logger,
    job_id: int | None = None,
) -> None:
    """Store the feature vectors sent with each detection, one row per (detection, algorithm).

    :param saved_detections: Each saved detection with the response it was saved from. The vectors in the
        responses must already have passed ``validate_detection_embeddings``.
    :param algorithms_known: The pipeline's registered algorithms, by key
    :param job_id: The job whose results these are, recorded on each new row

    The first vector stored for a detection and algorithm is kept; later ones are ignored. To replace
    vectors, delete the detections, or register the new ML model as a new algorithm.
    """
    embeddings: list[DetectionEmbedding] = []
    for detection, detection_resp in saved_detections:
        if not detection_resp.embeddings:
            continue
        embeddings += [
            DetectionEmbedding(
                detection=detection,
                algorithm=algorithms_known[embedding_resp.algorithm.key],
                project_id=detection.source_image.project_id,
                vector=embedding_resp.features,
                job_id=job_id,
            )
            for embedding_resp in detection_resp.embeddings
        ]
    # Insert in one fixed order, so two concurrent batches that share detections wait for each other
    # instead of deadlocking.
    embeddings.sort(key=lambda embedding: (embedding.detection_id, embedding.algorithm_id))
    if not embeddings:
        return
    DetectionEmbedding.objects.bulk_create(embeddings, batch_size=EMBEDDING_BATCH_SIZE, ignore_conflicts=True)
    logger.info(
        f"Sent {len(embeddings)} feature vectors to be stored; any detection that already had a vector from "
        "the same algorithm keeps it."
    )
