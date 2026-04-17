"""
Worker poll loop. Mode B (all-pipelines) per the design doc.

Iterates each of this container's registered pipeline slugs in turn, so the
slug for any given job is always the outer loop variable — no reverse lookup
from job_id → slug needed.

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

from api.api import pipeline_choices  # type: ignore[import-not-found]
from api.schemas import ProcessingServiceClientInfo  # type: ignore[import-not-found]

from .client import AntennaClient
from .runner import process_task

logger = logging.getLogger(__name__)


class Loop:
    def __init__(self, client: AntennaClient, client_info: ProcessingServiceClientInfo) -> None:
        self.client = client
        self.client_info = client_info
        self.shutdown = False
        self.poll_interval = float(os.environ["WORKER_POLL_INTERVAL_SECONDS"])
        self.batch_size = int(os.environ["WORKER_BATCH_SIZE"])

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
        """One poll cycle across all registered slugs. Returns True if any work was done."""
        did_work = False
        for slug in my_slugs:
            if self.shutdown:
                break
            job_ids = self.client.list_active_jobs(slug)
            for job_id in job_ids:
                if self.shutdown:
                    break
                tasks = self.client.reserve_tasks(job_id, self.batch_size, client_info=self.client_info)
                if not tasks:
                    continue
                did_work = True
                results = [process_task(task, slug) for task in tasks]
                ack = self.client.submit_results(job_id, results, client_info=self.client_info)
                logger.info(
                    "Job %s (%s): processed %d task(s), results_queued=%s",
                    job_id,
                    slug,
                    len(tasks),
                    ack.get("results_queued"),
                )
        return did_work
