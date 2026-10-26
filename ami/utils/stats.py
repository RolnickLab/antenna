"""Generic statistical helpers reusable across apps.

Kept independent of Django and any domain models so they can be unit-tested
in isolation and reused by other endpoints/jobs that need to express
uncertainty (Wilson CI) or correct an agreement rate for chance (kappa).
"""

from __future__ import annotations

import collections
import math

# z-score for a 95% two-sided confidence interval (Wilson score).
WILSON_Z_95 = 1.959963984540054


def wilson_interval(successes: int, total: int, z: float = WILSON_Z_95) -> tuple[float, float] | None:
    """Wilson score confidence interval for a binomial proportion.

    Returns ``(low, high)`` bounded to ``[0, 1]`` (rounded to 4 dp), or
    ``None`` when ``total`` is 0. Defaults to a 95% interval.

    The Wilson score interval is used instead of the normal approximation
    because the verified set is often tiny (single-digit counts), where the
    normal approximation produces bounds outside [0, 1] and understates the
    uncertainty. Wilson stays well-behaved at small n and at proportions
    near 0 or 1.

    Raises ``ValueError`` if ``successes`` is outside ``[0, total]`` — that
    can only come from a caller bug, and letting it through would make the
    sqrt term negative and crash deeper in with an opaque math-domain error.
    """
    if total <= 0:
        return None
    if not 0 <= successes <= total:
        raise ValueError(f"successes ({successes}) must be between 0 and total ({total})")
    phat = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (phat + z2 / (2 * total)) / denom
    margin = (z / denom) * math.sqrt(phat * (1 - phat) / total + z2 / (4 * total * total))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (round(low, 4), round(high, 4))


def cohens_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """Cohen's kappa for exact agreement between two raters.

    ``pairs`` is one ``(rater_a, rater_b)`` per item that both raters
    classified. Returns kappa rounded to 4 dp in ``[-1, 1]`` (negative =
    worse than chance), or ``None`` when there are no pairs or expected
    agreement is 1.0 (kappa undefined — a single category leaves no
    chance-agreement to correct for).

    Plain agreement rate rewards luck: in a project dominated by one common
    category, both raters agree most of the time just by both naming the
    common one. Kappa subtracts that chance agreement, so it answers "how
    much better than guessing do they agree" rather than "how often do they
    happen to match".
    """
    n = len(pairs)
    if n == 0:
        return None
    observed_agree = sum(1 for a, b in pairs if a == b) / n
    a_counts: collections.Counter = collections.Counter(a for a, _ in pairs)
    b_counts: collections.Counter = collections.Counter(b for _, b in pairs)
    expected_agree = sum((a_counts[key] / n) * (b_counts[key] / n) for key in set(a_counts) | set(b_counts))
    if expected_agree >= 1.0:
        return None
    return round((observed_agree - expected_agree) / (1 - expected_agree), 4)
