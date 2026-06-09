"""Helpers for scheduling cached-count recomputes after a transaction commits.

Wraps the per-connection dedup + ``transaction.on_commit`` plumbing that
``BaseModel.update_cached_counts`` and ``BaseQuerySet.update_cached_counts``
build on. The actual recompute body lives in each model's
``update_calculated_fields(save=True)`` implementation; this module only
handles scheduling.

Per-(model_label, pk) dedup means N writes affecting the same target row
collapse to one task, regardless of how many signal handlers fire in the
transaction. The dedup set lives on the active DB connection (thread-local
in Django's default setup) and is drained by a single ``on_commit`` hook.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import connection, transaction

logger = logging.getLogger(__name__)

_PENDING_ATTR = "_pending_cached_count_recomputes"


def schedule_recompute(model_label: str, pk: Any) -> None:
    """Queue a ``(model_label, pk)`` for recompute at the next commit.

    The pending set lives on the active DB connection; ``transaction.on_commit``
    fires the flush. ``_flush_pending_recomputes`` is idempotent — the first
    call drains the set; subsequent ones no-op — so we register on_commit on
    every call. That keeps us correct across transaction rollbacks (which
    discard registered on_commits but leave attributes on ``connection``
    untouched, e.g. between a rolled-back ``TestCase`` and a fresh
    ``TransactionTestCase``).

    Outside an atomic block, ``on_commit`` fires synchronously at
    registration time — so the ``add`` below must precede the
    ``transaction.on_commit`` call or the flush sees an empty set.
    """
    pending: set[tuple[str, Any]] | None = getattr(connection, _PENDING_ATTR, None)
    if pending is None:
        pending = set()
        setattr(connection, _PENDING_ATTR, pending)
    pending.add((model_label, pk))
    transaction.on_commit(_flush_pending_recomputes)


def _flush_pending_recomputes() -> None:
    """Drain the per-connection dedup set; dispatch one task per ``(model, pk)``."""
    from ami.main.tasks import recompute_cached_counts_task

    pending: set[tuple[str, Any]] = getattr(connection, _PENDING_ATTR, set())
    try:
        delattr(connection, _PENDING_ATTR)
    except AttributeError:
        pass
    for model_label, pk in pending:
        recompute_cached_counts_task.delay(model_label, pk)
