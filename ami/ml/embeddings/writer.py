"""Store the feature vectors a processing service returns with its detections."""

import collections
import logging

import numpy as np

from ami.main.models import DEFAULT_EMBEDDING_KEY, Detection
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.embedding import DetectionEmbedding, as_half_precision
from ami.ml.schemas import DetectionResponse

logger = logging.getLogger(__name__)

# Boxes are matched to responses at this precision, so a service that re-serialises the
# coordinates it was sent still lands its vectors on the same detections.
BOX_MATCH_DECIMALS = 3


def _box_key(source_image_id, coordinates) -> tuple:
    return (str(source_image_id), tuple(round(float(value), BOX_MATCH_DECIMALS) for value in coordinates))


class EmbeddingDimensionMismatch(PipelineNotConfigured):
    """A vector's length differs from the length its algorithm has produced before."""


def _check_embedding_dimensions(lengths_by_pair: dict[tuple[Algorithm, str], set[int]]) -> None:
    """Refuse vectors whose length differs from the one already stored for their (algorithm, key).

    Vectors of different lengths can never be compared, so each (algorithm, key) keeps one length,
    read from one existing row (an indexed lookup per pair). With no row yet, the batch must agree.
    """
    for (algorithm, key), lengths in lengths_by_pair.items():
        stored = DetectionEmbedding.objects.stored_length(algorithm.pk, key)
        if stored is None and len(lengths) > 1:
            raise EmbeddingDimensionMismatch(
                f"Algorithm {algorithm.key} sent vectors of several lengths under key '{key}' in one batch: "
                f"{sorted(lengths)}"
            )
        expected = stored if stored is not None else next(iter(lengths))
        wrong = lengths - {expected}
        if wrong:
            raise EmbeddingDimensionMismatch(
                f"Algorithm {algorithm.key} produces {expected}-dimension vectors under key '{key}'; "
                f"refusing vectors of length {sorted(wrong)}."
            )


def create_detection_embeddings(
    detections: list[Detection],
    detection_responses: list[DetectionResponse],
    algorithms_known: dict[str, Algorithm],
    logger: logging.Logger = logger,
    job_id: int | None = None,
) -> list[DetectionEmbedding]:
    """
    Store the feature vectors sent with each detection, one row per (detection, algorithm, key).

    Writes are insert-mostly (see ``DetectionEmbeddingQuerySet.store``): saving the same results
    twice changes nothing, and a new vector for a pair replaces the old one. Only
    ``DetectionEmbedding`` rows are written, never a classification, so no determination can
    change. A vector with a value half precision cannot hold (NaN, infinity, beyond 65504) is
    skipped with a warning.

    Responses are matched to ``detections`` by image and box (see ``BOX_MATCH_DECIMALS``), the
    key ``get_or_create_detection`` reuses detections by, because detection creation returns
    existing detections ahead of new ones and pairing by position would swap vectors. An
    algorithm key the pipeline has not registered raises ``PipelineNotConfigured``, as it does
    for classifications, and a vector whose length differs from its algorithm's raises
    ``EmbeddingDimensionMismatch``. ``job_id`` records the job whose results stored each vector.
    Returns the embeddings that were sent to the store (written or unchanged).
    """
    by_box = {
        _box_key(detection.source_image_id, detection.bbox): detection
        for detection in detections
        if detection.bbox is not None
    }
    embeddings: dict[tuple[int, int], DetectionEmbedding] = {}
    lengths_by_pair: dict[tuple[Algorithm, str], set[int]] = collections.defaultdict(set)
    unmatched = not_finite = 0
    for detection_resp in detection_responses:
        if detection_resp.bbox is None or not detection_resp.embeddings:
            continue
        detection = by_box.get(_box_key(detection_resp.source_image_id, detection_resp.bbox.dict().values()))
        if detection is None:
            unmatched += 1
            continue
        for embedding_resp in detection_resp.embeddings:
            try:
                algorithm = algorithms_known[embedding_resp.algorithm.key]
            except KeyError as err:
                raise PipelineNotConfigured(
                    f"Embedding algorithm {embedding_resp.algorithm.key} is not a known algorithm. "
                    "The processing service must declare it in the /info endpoint. "
                    f"Known algorithms: {list(algorithms_known.keys())}"
                ) from err
            if not np.isfinite(as_half_precision(embedding_resp.features)).all():
                not_finite += 1
                continue
            lengths_by_pair[(algorithm, DEFAULT_EMBEDDING_KEY)].add(len(embedding_resp.features))
            embeddings[(detection.pk, algorithm.pk)] = DetectionEmbedding(
                detection=detection,
                algorithm=algorithm,
                key=DEFAULT_EMBEDDING_KEY,
                vector=embedding_resp.features,
                job_id=job_id,
            )

    _check_embedding_dimensions(lengths_by_pair)

    if unmatched:
        logger.warning(f"Skipped the vectors of {unmatched} returned boxes that match no stored detection.")
    if not_finite:
        logger.warning(f"Skipped {not_finite} vectors with values a half-precision vector cannot store.")
    if embeddings:
        written, unchanged = DetectionEmbedding.objects.store(embeddings.values())
        logger.info(f"Stored {written} feature vectors ({unchanged} unchanged) for {len(detections)} detections.")
    return list(embeddings.values())
