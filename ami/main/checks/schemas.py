"""Shared result schemas for integrity and health checks.

A check is any function that inspects some slice of state and returns an
:class:`IntegrityCheckResult`. Reconciliation checks populate ``fixed``
with the number of rows actually mutated; observation checks (e.g.
logging a snapshot) keep ``fixed`` at 0 and use ``unfixable`` to count
items the check could not complete for.
"""

import dataclasses


@dataclasses.dataclass
class IntegrityCheckResult:
    """Summary of a single integrity or health check pass.

    Attributes:
        checked: Rows / items the check inspected this pass.
        fixed: Rows the check mutated to a correct state. Observation-only
            checks must leave this at 0 — ``fixed`` means state was altered.
        unfixable: Rows the check inspected but could not repair or observe
            (for observation checks this counts errors per item).
    """

    checked: int = 0
    fixed: int = 0
    unfixable: int = 0
