"""Deterministic feature vectors, so the template returns vectors without model weights.

A vector depends only on the algorithm, the capture and the box: the same box always gets the
same vector, and different boxes get different ones. Lengths are fixed per algorithm, as they
are for a real model.
"""

import hashlib
import math

from .schemas import AlgorithmReference, BoundingBox, EmbeddingResponse

# Length of the vectors from the constant feature extractor.
EXTRACTOR_VECTOR_LENGTH = 8
# Length of the vectors a classifier returns as its own features (features_for_all_detections).
CLASSIFIER_VECTOR_LENGTH = 4


def deterministic_vector(seed: str, length: int) -> list[float]:
    """A unit-length vector of ``length`` values in [-1, 1], derived from ``seed``."""
    values: list[float] = []
    block = 0
    while len(values) < length:
        digest = hashlib.sha256(f"{block}:{seed}".encode()).digest()
        values.extend(byte / 127.5 - 1.0 for byte in digest)
        block += 1
    values = values[:length]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def embedding_for(
    algorithm: AlgorithmReference, source_image_id: str, bbox: BoundingBox | None, length: int
) -> EmbeddingResponse:
    box = bbox.to_string() if bbox else "none"
    return EmbeddingResponse(
        features=deterministic_vector(f"{algorithm.key}:{source_image_id}:{box}", length),
        algorithm=algorithm,
    )
