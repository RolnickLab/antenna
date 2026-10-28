"""
Helpers for the per-class arrays a classifier returns: ``logits`` and ``scores``.

For a classifier with thousands of classes these arrays are most of the database's size,
so only one copy of the information is stored. Scores equal softmax(logits) for classifiers
that report real logits, so the scores array is left out when it can be recomputed.
"""

import math

# Largest difference between a stored score and softmax(logits) that still counts as equal.
# Scores computed by the model in float32 differ from a float64 softmax by up to ~1e-5.
SOFTMAX_TOLERANCE = 1e-4


def softmax(logits: list[float]) -> list[float]:
    top = max(logits)
    exps = [math.exp(x - top) for x in logits]
    total = sum(exps)
    return [x / total for x in exps]


def logits_are_probabilities(logits: list[float]) -> bool:
    """True when ``logits`` holds a probability distribution rather than raw logits.

    Some classifications store the softmax output in both ``scores`` and ``logits``.
    Real logits from a many-class model do not sum to 1.
    """
    return min(logits) >= 0.0 and max(logits) <= 1.0 and abs(sum(logits) - 1.0) < 1e-3


def arrays_to_store(
    scores: list[float] | None, logits: list[float] | None
) -> tuple[list[float] | None, list[float] | None]:
    """Return the ``(scores, logits)`` to save, dropping whichever array duplicates the other.

    - Logits that are a copy of the scores are dropped: they are not logits.
    - Scores equal to softmax(logits) are dropped: ``Classification.scores_or_softmax()``
      recomputes them.
    - Otherwise both are kept, for example a model whose scores are calibrated.
    """
    if not scores or not logits or len(scores) != len(logits):
        return scores, logits
    if logits == scores or logits_are_probabilities(logits):
        return scores, None
    if max(abs(p - s) for p, s in zip(softmax(logits), scores)) <= SOFTMAX_TOLERANCE:
        return None, logits
    return scores, logits
