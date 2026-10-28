"""
Which per-class arrays a classification stores, and how its scores are read back.

For a classifier with thousands of classes the ``scores`` and ``logits`` arrays are most of
the database. Scores equal softmax(logits) for classifiers that report real logits, so only
the logits are stored for them and the scores are recomputed on read.
"""

import typing

import numpy as np

from ami.utils.stats import softmax

# Relative and absolute tolerance for "the scores are softmax(logits)". Scores computed in
# float32 by the model differ from a float64 softmax by at most ~3e-6 (measured on production
# rows); a relative check keeps calibrated scores of a many-class model, which are all tiny.
SOFTMAX_RTOL = 1e-3
SOFTMAX_ATOL = 1e-9


def logits_are_probabilities(logits: typing.Sequence[float]) -> bool:
    """True when ``logits`` holds a probability distribution rather than raw logits.

    Some classifications store the softmax output in both ``scores`` and ``logits``. Real
    logits from a many-class model do not sum to 1. A two-class model's real logits can,
    which only means both arrays are kept.
    """
    values = np.asarray(logits, dtype=float)
    return bool(values.size and values.min() >= 0.0 and values.max() <= 1.0 and abs(values.sum() - 1.0) < 1e-3)


def arrays_to_store(
    scores: list[float] | None, logits: list[float] | None
) -> tuple[list[float] | None, list[float] | None]:
    """Return the ``(scores, logits)`` to save, leaving out an array the other one makes redundant.

    - Logits that are a probability distribution are left out: they are not logits.
    - Scores equal to softmax(logits), with the same top class, are left out.
    - Otherwise both are kept, for example a model whose scores are calibrated.
    """
    if not scores or not logits or len(scores) != len(logits):
        return scores, logits
    if logits_are_probabilities(logits):
        return scores, None
    stored = np.asarray(scores, dtype=float)
    derived = softmax(logits)
    if int(stored.argmax()) == int(derived.argmax()) and np.allclose(
        derived, stored, rtol=SOFTMAX_RTOL, atol=SOFTMAX_ATOL
    ):
        return None, logits
    return scores, logits


def probabilities(scores: list[float] | None, logits: list[float] | None) -> list[float]:
    """The per-class probabilities: the stored scores, else softmax(logits), else empty."""
    if scores:
        return scores
    if logits:
        return list(logits) if logits_are_probabilities(logits) else softmax(logits).tolist()
    return []
