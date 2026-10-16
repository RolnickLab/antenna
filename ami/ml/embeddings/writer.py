"""Store the feature vectors a processing service returns with its detections."""

from __future__ import annotations

import collections
import contextlib
import dataclasses
import logging
import typing
import zlib

import numpy as np
from django.db import connection, transaction

from ami.main.models import Detection
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.embedding import DetectionEmbedding, as_half_precision
from ami.ml.schemas import DetectionResponse, PipelineResultsResponse

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models.pipeline import Pipeline

logger = logging.getLogger(__name__)


class EmbeddingDimensionMismatch(PipelineNotConfigured):
    """A vector's length differs from the length its algorithm has produced before."""


# The first number of the two-number advisory lock, so these locks cannot collide with others keyed by an id.
_FIRST_WRITE_LOCK_SPACE = zlib.crc32(b"ml_detectionembedding first write") & 0x7FFFFFFF


def _lock_first_write(algorithm: Algorithm) -> None:
    """Serialise the first writers of one algorithm's vectors until the surrounding transaction ends."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [_FIRST_WRITE_LOCK_SPACE, algorithm.pk])


def _check_embedding_dimensions(
    lengths_by_algorithm: dict[Algorithm, set[int]], stored_by_algorithm: dict[Algorithm, int | None]
) -> None:
    """Refuse vectors whose length differs from the one already stored for their algorithm.

    Vectors of different lengths can never be compared, so each algorithm keeps one length.
    With none stored yet, the batch must agree on one.
    """
    for algorithm, lengths in lengths_by_algorithm.items():
        stored = stored_by_algorithm[algorithm]
        if stored is None and len(lengths) > 1:
            raise EmbeddingDimensionMismatch(
                f"Algorithm {algorithm.key} sent vectors of several lengths in one batch: {sorted(lengths)}"
            )
        expected = stored if stored is not None else next(iter(lengths))
        wrong = lengths - {expected}
        if wrong:
            raise EmbeddingDimensionMismatch(
                f"Algorithm {algorithm.key} produces {expected}-dimension vectors; "
                f"refusing vectors of length {sorted(wrong)}."
            )


@dataclasses.dataclass
class EmbeddingStoreResult:
    """What one batch of returned vectors did: the rows sent to the store and how each vector fared."""

    embeddings: list[DetectionEmbedding] = dataclasses.field(default_factory=list)
    written: int = 0
    unchanged: int = 0
    unmatched: int = 0
    not_finite: int = 0


def create_detection_embeddings(
    saved_detections: list[tuple[Detection, DetectionResponse]],
    algorithms_known: dict[str, Algorithm],
    logger: logging.Logger = logger,
    job_id: int | None = None,
) -> list[DetectionEmbedding]:
    """
    Store the feature vectors sent with each detection, one row per (detection, algorithm).

    Each vector is stored on the detection its response was saved as, from the pairs
    ``create_detections`` returns, so a vector can never land on another box (#1436). Writes are
    insert-mostly (see ``DetectionEmbeddingQuerySet.store``): saving the same results twice
    changes nothing, and a new vector from an algorithm replaces its old one. Only
    ``DetectionEmbedding`` rows are written, never a classification, so no determination can
    change. A vector with a value half precision cannot hold (NaN, infinity, beyond 65504) is
    skipped with a warning. An algorithm key the pipeline has not registered raises
    ``PipelineNotConfigured``, as it does for classifications, and a vector whose length differs
    from its algorithm's raises ``EmbeddingDimensionMismatch``. ``job_id`` records the job whose
    results stored each vector. Returns the embeddings that were sent to the store (written or
    unchanged).
    """
    return store_detection_embeddings(saved_detections, algorithms_known, logger, job_id).embeddings


def store_detection_embeddings(
    saved_detections: list[tuple[Detection, DetectionResponse]],
    algorithms_known: dict[str, Algorithm],
    logger: logging.Logger = logger,
    job_id: int | None = None,
) -> EmbeddingStoreResult:
    """Store the vectors of each (detection, response) pair, by the rules of ``create_detection_embeddings``."""
    embeddings: dict[tuple[int, int], DetectionEmbedding] = {}
    lengths_by_algorithm: dict[Algorithm, set[int]] = collections.defaultdict(set)
    not_finite = repeated = 0
    for detection, detection_resp in saved_detections:
        if not detection_resp.embeddings:
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
            lengths_by_algorithm[algorithm].add(len(embedding_resp.features))
            row_key = (detection.pk, algorithm.pk)
            # One row per (detection, algorithm): a second vector replaces the first.
            repeated += row_key in embeddings
            embeddings[row_key] = DetectionEmbedding(
                detection=detection,
                algorithm=algorithm,
                vector=embedding_resp.features,
                job_id=job_id,
            )

    stored_by_algorithm = {
        algorithm: DetectionEmbedding.objects.stored_length(algorithm.pk) for algorithm in lengths_by_algorithm
    }
    first_writes = [algorithm for algorithm, stored in stored_by_algorithm.items() if stored is None]
    result = EmbeddingStoreResult(embeddings=list(embeddings.values()), not_finite=not_finite)

    with contextlib.ExitStack() as stack:
        if first_writes:
            # Hold the lock until the vectors are committed, so a concurrent first writer sees them.
            stack.enter_context(transaction.atomic())
            # A fixed order, so two batches that share new algorithms cannot each hold one lock and wait for the other.
            for algorithm in sorted(first_writes, key=lambda algorithm: algorithm.pk):
                _lock_first_write(algorithm)
                stored_by_algorithm[algorithm] = DetectionEmbedding.objects.stored_length(algorithm.pk)
        _check_embedding_dimensions(lengths_by_algorithm, stored_by_algorithm)

        if repeated:
            logger.warning(
                f"Skipped {repeated} vectors: an algorithm sent more than one vector for a detection, "
                "and only the last one is kept."
            )
        if not_finite:
            logger.warning(f"Skipped {not_finite} vectors with values a half-precision vector cannot store.")
        if embeddings:
            result.written, result.unchanged = DetectionEmbedding.objects.store(embeddings.values())
            logger.info(
                f"Stored {result.written} feature vectors ({result.unchanged} unchanged) "
                f"for {len(saved_detections)} detections."
            )
    return result


def _box_key(source_image_id, coordinates) -> tuple:
    """Exact coordinates, the identity ``get_or_create_detection`` reuses detections by."""
    return (str(source_image_id), tuple(float(value) for value in coordinates))


def save_embedding_results(
    response: PipelineResultsResponse,
    job: Job | None,
    pipeline: Pipeline,
) -> EmbeddingStoreResult:
    """Store only the vectors of a feature-only response, on detections that already exist.

    A feature-only processing service returns the detections it was sent, unchanged and still
    naming the detector that made them, with an embedding attached and no classifications. Each
    returned detection is matched by capture and exact box to a stored valid detection; nothing else
    is written: no detection, classification or occurrence is created, and the echoed detector
    reference is ignored. A returned box that matches no stored detection, or more than one, is
    counted in ``unmatched`` and logged, never created or guessed. An embedding that names an
    algorithm outside ``pipeline`` raises ``PipelineNotConfigured``, and a vector of the wrong
    length for its algorithm raises ``EmbeddingDimensionMismatch``.
    """
    capture_ids = {int(detection.source_image_id) for detection in response.detections}
    by_box: dict[tuple, list[Detection]] = collections.defaultdict(list)
    for detection in Detection.objects.valid().filter(source_image_id__in=capture_ids):
        if detection.bbox is not None:
            by_box[_box_key(detection.source_image_id, detection.bbox)].append(detection)
    saved_detections: list[tuple[Detection, DetectionResponse]] = []
    unmatched = 0
    for detection_resp in response.detections:
        if detection_resp.bbox is None or not detection_resp.embeddings:
            continue
        candidates = by_box.get(_box_key(detection_resp.source_image_id, detection_resp.bbox.as_coords()), [])
        if len(candidates) == 1:
            saved_detections.append((candidates[0], detection_resp))
        else:
            unmatched += 1

    job_logger = job.logger if job else logger
    if unmatched:
        job_logger.warning(f"Skipped the vectors of {unmatched} returned boxes that match no single stored detection.")
    algorithms_known = {algorithm.key: algorithm for algorithm in pipeline.algorithms.all()}
    result = store_detection_embeddings(saved_detections, algorithms_known, job_logger, job.pk if job else None)
    result.unmatched = unmatched
    return result
