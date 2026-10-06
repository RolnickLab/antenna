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

from ami.main.models import DEFAULT_EMBEDDING_KEY, Detection
from ami.ml.exceptions import PipelineNotConfigured
from ami.ml.models.algorithm import Algorithm
from ami.ml.models.embedding import DetectionEmbedding, as_half_precision
from ami.ml.schemas import DetectionResponse, PipelineResultsResponse

if typing.TYPE_CHECKING:
    from ami.jobs.models import Job
    from ami.ml.models.pipeline import Pipeline

logger = logging.getLogger(__name__)


def _box_key(source_image_id, coordinates) -> tuple:
    """Exact coordinates, the identity ``get_or_create_detection`` reuses detections by."""
    return (str(source_image_id), tuple(float(value) for value in coordinates))


class EmbeddingDimensionMismatch(PipelineNotConfigured):
    """A vector's length differs from the length its algorithm has produced before."""


def _lock_first_write(algorithm: Algorithm, key: str) -> None:
    """Serialise first writers of one (algorithm, key) until the surrounding transaction ends."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [algorithm.pk, zlib.crc32(key.encode()) & 0x7FFFFFFF])


def _check_embedding_dimensions(
    lengths_by_pair: dict[tuple[Algorithm, str], set[int]], stored_by_pair: dict[tuple[Algorithm, str], int | None]
) -> None:
    """Refuse vectors whose length differs from the one already stored for their (algorithm, key).

    Vectors of different lengths can never be compared, so each (algorithm, key) keeps one length.
    With none stored yet, the batch must agree on one.
    """
    for (algorithm, key), lengths in lengths_by_pair.items():
        stored = stored_by_pair[(algorithm, key)]
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


@dataclasses.dataclass
class EmbeddingStoreResult:
    """What one batch of returned vectors did: the rows sent to the store and how each vector fared."""

    embeddings: list[DetectionEmbedding] = dataclasses.field(default_factory=list)
    written: int = 0
    unchanged: int = 0
    unmatched: int = 0
    not_finite: int = 0


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

    Responses are matched to ``detections`` by image and box (by exact coordinates), the
    key ``get_or_create_detection`` reuses detections by, because detection creation returns
    existing detections ahead of new ones and pairing by position would swap vectors. An
    algorithm key the pipeline has not registered raises ``PipelineNotConfigured``, as it does
    for classifications, and a vector whose length differs from its algorithm's raises
    ``EmbeddingDimensionMismatch``. ``job_id`` records the job whose results stored each vector.
    Returns the embeddings that were sent to the store (written or unchanged).
    """
    return store_detection_embeddings(
        detections, detection_responses, algorithms_known, DEFAULT_EMBEDDING_KEY, logger, job_id
    ).embeddings


def store_detection_embeddings(
    detections: list[Detection],
    detection_responses: list[DetectionResponse],
    algorithms_known: dict[str, Algorithm],
    key: str,
    logger: logging.Logger = logger,
    job_id: int | None = None,
) -> EmbeddingStoreResult:
    """Match returned vectors to ``detections`` by image and box and store them under ``key``.

    The matching, validation and storing rules are those of ``create_detection_embeddings``.
    """
    by_box: dict[tuple, list[Detection]] = collections.defaultdict(list)
    for detection in detections:
        if detection.bbox is not None:
            by_box[_box_key(detection.source_image_id, detection.bbox)].append(detection)
    embeddings: dict[tuple[int, int, str], DetectionEmbedding] = {}
    lengths_by_pair: dict[tuple[Algorithm, str], set[int]] = collections.defaultdict(set)
    unmatched = not_finite = 0
    for detection_resp in detection_responses:
        if detection_resp.bbox is None or not detection_resp.embeddings:
            continue
        box_key = _box_key(detection_resp.source_image_id, detection_resp.bbox.dict().values())
        candidates = by_box.get(box_key, [])
        if len(candidates) > 1:
            logger.warning(
                f"Skipped the vectors of capture {box_key[0]} box {box_key[1]}: "
                f"{len(candidates)} stored detections share that box."
            )
        if len(candidates) != 1:
            unmatched += 1
            continue
        detection = candidates[0]
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
            lengths_by_pair[(algorithm, key)].add(len(embedding_resp.features))
            embeddings[(detection.pk, algorithm.pk, key)] = DetectionEmbedding(
                detection=detection,
                algorithm=algorithm,
                key=key,
                vector=embedding_resp.features,
                job_id=job_id,
            )

    stored_by_pair = {pair: DetectionEmbedding.objects.stored_length(pair[0].pk, pair[1]) for pair in lengths_by_pair}
    first_writes = [pair for pair, stored in stored_by_pair.items() if stored is None]
    result = EmbeddingStoreResult(embeddings=list(embeddings.values()), unmatched=unmatched, not_finite=not_finite)

    with contextlib.ExitStack() as stack:
        if first_writes:
            # Hold the lock until the vectors are committed, so a concurrent first writer sees them.
            stack.enter_context(transaction.atomic())
            for algorithm, pair_key in first_writes:
                _lock_first_write(algorithm, pair_key)
                stored_by_pair[(algorithm, pair_key)] = DetectionEmbedding.objects.stored_length(
                    algorithm.pk, pair_key
                )
        _check_embedding_dimensions(lengths_by_pair, stored_by_pair)

        if unmatched:
            logger.warning(f"Skipped the vectors of {unmatched} returned boxes that match no single stored detection.")
        if not_finite:
            logger.warning(f"Skipped {not_finite} vectors with values a half-precision vector cannot store.")
        if embeddings:
            result.written, result.unchanged = DetectionEmbedding.objects.store(embeddings.values())
            logger.info(
                f"Stored {result.written} feature vectors ({result.unchanged} unchanged) "
                f"for {len(detections)} detections."
            )
    return result


def save_embedding_results(
    response: PipelineResultsResponse,
    job: Job | None,
    pipeline: Pipeline,
    key: str = DEFAULT_EMBEDDING_KEY,
) -> EmbeddingStoreResult:
    """Store only the vectors of a feature-only response, on detections that already exist.

    A feature-only processing service returns the detections it was sent, unchanged and still
    naming the detector that made them, with an embedding attached and no classifications. Each
    returned detection is matched by capture and box to a stored valid detection; nothing else is
    written: no detection, classification or occurrence is created, and the echoed detector
    reference is ignored. A returned box with no stored detection is counted in ``unmatched`` and
    logged, never created. An embedding that names an algorithm outside ``pipeline`` raises
    ``PipelineNotConfigured``, and a vector of the wrong length for its (algorithm, key) raises
    ``EmbeddingDimensionMismatch``.
    """
    capture_ids = {int(detection.source_image_id) for detection in response.detections}
    detections = list(Detection.objects.valid().filter(source_image_id__in=capture_ids))
    algorithms_known = {algorithm.key: algorithm for algorithm in pipeline.algorithms.all()}
    job_logger = job.logger if job else logger
    return store_detection_embeddings(
        detections, response.detections, algorithms_known, key, job_logger, job.pk if job else None
    )
