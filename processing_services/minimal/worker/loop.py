"""
Worker poll loop. Mode B (all-pipelines) per the design doc.

# TODO(follow-up): add --pipeline <slug> flag (mode A) so multiple workers can
#   run side-by-side as competing consumers for the same pipeline.
# TODO(follow-up): add --job-id <id> flag (mode C) for one-shot drain-and-exit
#   runs, for test_ml_job_e2e-style harnesses.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from collections import defaultdict

from api.api import pipeline_choices  # type: ignore[import-not-found]

from .client import AntennaClient
from .runner import process_task

logger = logging.getLogger(__name__)


class Loop:
    def __init__(self, client: AntennaClient, client_info: dict) -> None:
        self.client = client
        self.client_info = client_info
        self.shutdown = False
        self.poll_interval = float(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "2.0"))
        self.batch_size = int(os.environ.get("WORKER_BATCH_SIZE", "4"))

    def _install_signal_handlers(self) -> None:
        def _stop(signum, frame):  # noqa: ARG001
            logger.info("Received signal %s, shutting down", signum)
            self.shutdown = True

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)

    def run(self) -> None:
        self._install_signal_handlers()
        my_slugs = list(pipeline_choices.keys())
        logger.info("Polling for jobs on pipelines: %s", my_slugs)

        while not self.shutdown:
            try:
                iterated = self._iterate(my_slugs)
            except Exception:
                # Log full traceback and keep going; a faulty poll shouldn't kill the worker.
                logger.exception("Poll iteration failed")
                iterated = False
            if not iterated:
                time.sleep(self.poll_interval)

    def _iterate(self, my_slugs: list[str]) -> bool:
        """One poll cycle. Returns True if any work was done."""
        job_ids = self.client.list_active_jobs(my_slugs)
        if not job_ids:
            return False

        did_work = False
        for job_id in job_ids:
            tasks = self.client.reserve_tasks(job_id, self.batch_size, client_info=self.client_info)
            if not tasks:
                continue
            did_work = True

            # Group tasks by pipeline slug. Antenna doesn't return the slug on the
            # task itself, but all tasks in a job share the same pipeline — we know
            # which slug because we filtered list_active_jobs by it. Reverse-lookup
            # from job_id → slug by re-listing, falling back to per-slug try.
            slug = self._slug_for_job(job_id, my_slugs)
            if slug is None:
                logger.warning("Could not determine pipeline slug for job %s; skipping %d task(s)", job_id, len(tasks))
                continue

            results = [process_task(task, slug) for task in tasks]
            ack = self.client.submit_results(job_id, results, client_info=self.client_info)
            logger.info(
                "Job %s: processed %d task(s), results_queued=%s",
                job_id,
                len(tasks),
                ack.get("results_queued"),
            )
        return did_work

    def _slug_for_job(self, job_id: int, my_slugs: list[str]) -> str | None:
        """Which of our registered slugs does this job belong to?

        One GET per slug is wasteful but this is a stub — fine for now. Cache
        in memory per-iteration since list_active_jobs just ran.
        """
        cache: dict[str, set[int]] = defaultdict(set)
        for slug in my_slugs:
            # Ask Antenna for just this slug's active jobs; membership → slug.
            jobs = self.client.list_active_jobs([slug])
            cache[slug].update(jobs)
            if job_id in jobs:
                return slug
        return None
