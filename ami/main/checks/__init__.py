"""Data integrity checks for the main app.

Each module under this package defines one or more integrity check pairs:
a ``get_*`` function returning a queryset of affected rows, and a
``reconcile_*`` function that attempts to repair them. Both are exported
from this package so callers can compose individual checks from
management commands, post-job hooks, and periodic Celery tasks.
"""

from ami.main.checks.occurrences import (
    IntegrityCheckResult,
    get_occurrences_missing_determination,
    reconcile_missing_determinations,
)

__all__ = [
    "IntegrityCheckResult",
    "get_occurrences_missing_determination",
    "reconcile_missing_determinations",
]
