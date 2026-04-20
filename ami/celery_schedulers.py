"""Celery beat scheduler with a Docker-healthcheck-friendly heartbeat file.

Why this module exists
----------------------
Docker's default ``restart: unless-stopped`` only catches process death, not a
frozen scheduler thread. On 2026-04-16 the celerybeat container on ami-live
showed "Up 10 hours" in ``docker ps`` with four live PIDs and
``RestartCount=0``, yet its last log line was "Sending due task
celery.check_processing_services_online" twelve hours earlier — a Redis
connection blip had deadlocked the connection-pool lock and the scheduler
thread never recovered. The 15-minute ``jobs_health_check`` beat task stopped
firing, and stuck job 2421 was never reaped.

To let Docker flip the container to ``unhealthy`` on that failure mode, we
need a heartbeat signal that proves the scheduler's main loop is progressing.
Constraints:

- Beat does not answer ``celery inspect ping`` (that's a worker control
  message), so we can't reuse the worker healthcheck.
- We use ``DatabaseScheduler`` from ``django_celery_beat``, which keeps the
  schedule in Postgres, so there is no on-disk schedule file whose mtime
  would update naturally.
- A plain Celery task written from a worker would touch a file in the
  **worker's** filesystem, not beat's — Docker healthchecks read files
  inside the checked container.

So: override ``DatabaseScheduler.tick()`` to touch ``/tmp/beat-heartbeat``
on every iteration. ``tick()`` runs inside the beat process itself, so the
file lives in the beat container. If the scheduler loop hangs anywhere
(Redis pool lock, DB query, sync deadlock), ``tick()`` stops returning and
the file goes stale within ~60 s. The healthcheck
(``compose/*/django/celery/healthcheck-beat.sh``) fails, Docker marks the
container ``unhealthy``, and autoheal restarts it.

Activation
----------
Wired in via ``CELERY_BEAT_SCHEDULER`` in ``config/settings/base.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from django_celery_beat.schedulers import DatabaseScheduler

logger = logging.getLogger(__name__)

HEARTBEAT_PATH = Path("/tmp/beat-heartbeat")


class HeartbeatDatabaseScheduler(DatabaseScheduler):
    """DatabaseScheduler that touches a heartbeat file on every tick.

    Each call to ``tick()`` represents one cycle of the scheduler's main loop:
    evaluate due tasks, enqueue them, return the seconds until the next tick.
    If any step in that cycle hangs (e.g. a Redis or DB call blocks forever),
    ``tick()`` stops returning, the file mtime stops advancing, and the Docker
    healthcheck flips the container to ``unhealthy`` within ~2 minutes.

    We touch the file *before* delegating to ``super().tick()`` so a successful
    iteration of the loop itself is what proves liveness; if the heartbeat
    write ever fails (disk full, permission error), we log at warning level
    but don't re-raise — an I/O problem writing ``/tmp`` shouldn't take down
    the scheduler. Docker will eventually mark the container unhealthy on the
    stale file, which is the right outcome.
    """

    def tick(self, *args, **kwargs):
        try:
            HEARTBEAT_PATH.touch()
        except OSError as exc:
            logger.warning("beat heartbeat touch failed: %s", exc)
        return super().tick(*args, **kwargs)
