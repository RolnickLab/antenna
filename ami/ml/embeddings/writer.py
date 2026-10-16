"""Store the feature vectors a processing service returns with its detections."""

import logging

from ami.main.models import Detection
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models.algorithm import Algorithm, get_known_algorithm
from ami.ml.models.embedding import EMBEDDING_BATCH_SIZE, DetectionEmbedding
from ami.ml.schemas import DetectionResponse

logger = logging.getLogger(__name__)


class EmbeddingDimensionMismatch(PipelineNotConfigured):
    """Raised when a vector's length is not the length its algorithm declares."""


def validate_detection_embeddings(
    detection_responses: list[DetectionResponse], algorithms_known: dict[str, Algorithm]
) -> None:
    """Raise if any vector in these results cannot be stored. Call it before saving anything.

    Each vector must come from an algorithm registered for the pipeline (else ``PipelineNotConfigured``)
    that declares the length of its vectors, and must have that length (else ``EmbeddingDimensionMismatch``).
    Values out of range and repeated algorithms are already rejected by the results schema.
    """
    for detection_resp in detection_responses:
        for embedding_resp in detection_resp.embeddings or []:
            algorithm = get_known_algorithm(algorithms_known, embedding_resp.algorithm.key, "Embedding")
            if algorithm.embedding_dimensions is None:
                raise EmbeddingDimensionMismatch(
                    f"Algorithm {algorithm.key} sent a feature vector but declares no vector length. Its processing "
                    "service must declare embedding_dimensions for it in /info, then register its pipelines again."
                )
            if len(embedding_resp.features) != algorithm.embedding_dimensions:
                raise EmbeddingDimensionMismatch(
                    f"Algorithm {algorithm.key} declares {algorithm.embedding_dimensions}-dimension vectors "
                    f"but sent one of length {len(embedding_resp.features)}."
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
    vectors, delete the detections, or register the new model as a new algorithm.
    """
    embeddings: list[DetectionEmbedding] = []
    for detection, detection_resp in saved_detections:
        if not detection_resp.embeddings:
            continue
        project_id = detection.source_image.project_id
        if project_id is None:
            raise ValueError(
                f"Capture #{detection.source_image_id} belongs to no project, "
                "so the feature vectors of its detections cannot be stored."
            )
        embeddings += [
            DetectionEmbedding(
                detection=detection,
                algorithm=algorithms_known[embedding_resp.algorithm.key],
                project_id=project_id,
                vector=embedding_resp.features,
                job_id=job_id,
            )
            for embedding_resp in detection_resp.embeddings
        ]
    # Insert in one fixed order, so two concurrent batches that share detections wait for each other
    # instead of deadlocking.
    embeddings.sort(key=lambda embedding: (embedding.detection_id, embedding.algorithm_id))
    DetectionEmbedding.objects.bulk_create(embeddings, batch_size=EMBEDDING_BATCH_SIZE, ignore_conflicts=True)
    logger.info(
        f"Stored feature vectors for {len(saved_detections)} detections: {len(embeddings)} sent, "
        "keeping any vector already stored for the same detection and algorithm."
    )
