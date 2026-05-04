"""Integrity and health check primitives shared across apps.

Sub-modules in this package (added by per-domain check PRs such as
``ami.main.checks.occurrences`` in #1188) define ``get_*`` and
``reconcile_*`` function pairs. The shared result schema lives in
:mod:`ami.main.checks.schemas` so reconciliation and observation checks
across apps return the same shape.
"""

from ami.main.checks.schemas import IntegrityCheckResult

__all__ = ["IntegrityCheckResult"]
