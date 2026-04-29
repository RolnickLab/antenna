"""
HTTP client for the Antenna job-queue REST API.

Thin wrapper around requests.Session with a single retry policy and a single
auth header. All three endpoints (list active jobs, reserve tasks, submit
results) are thin wrappers around one POST or GET call — no attempt at
connection pooling tricks beyond what Session gives for free.
"""

from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .schemas import PipelineProcessingTask, PipelineTaskResult, ProcessingServiceClientInfo, TasksResponse

logger = logging.getLogger(__name__)


class AntennaClient:
    def __init__(self, api_url: str, auth_header: str, timeout: float = 30.0) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": auth_header})

        # Retry only on 5xx and network-level failures. 4xx is a programming
        # error we want to see immediately, not paper over.
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def list_active_jobs(self, pipeline_slug: str) -> list[int]:
        """
        Find STARTED job ids for a single pipeline slug.

        Calls GET /jobs/?pipeline__slug=<slug>&status=STARTED&ids_only=true.
        The server's `pipeline` filter expects a DB id; `pipeline__slug` is
        the slug-based alias exposed by JobFilterSet.
        """
        try:
            resp = self.session.get(
                f"{self.api_url}/api/v2/jobs/",
                params={"pipeline__slug": pipeline_slug, "status": "STARTED", "ids_only": "true"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("list_active_jobs failed for pipeline=%s: %s", pipeline_slug, e)
            return []

        payload = resp.json()
        # `ids_only=true` returns a flat list. Some list endpoints return
        # {"results": [...]}; handle both.
        entries = payload if isinstance(payload, list) else payload.get("results", [])
        ids: set[int] = set()
        for entry in entries:
            if isinstance(entry, dict) and "id" in entry:
                ids.add(int(entry["id"]))
            elif isinstance(entry, int):
                ids.add(entry)
        return sorted(ids)

    def reserve_tasks(
        self,
        job_id: int,
        batch_size: int,
        client_info: ProcessingServiceClientInfo | None = None,
    ) -> list[PipelineProcessingTask]:
        """
        POST /jobs/{id}/tasks/ — reserve up to batch_size tasks from the NATS
        queue for the given job. Antenna proxies NATS internally; we never
        touch NATS from here.
        """
        body: dict = {"batch_size": batch_size}
        if client_info is not None:
            body["client_info"] = client_info.model_dump(mode="json")
        resp = self.session.post(
            f"{self.api_url}/api/v2/jobs/{job_id}/tasks/",
            json=body,
            timeout=self.timeout,
        )
        if resp.status_code == 503:
            logger.info("Task queue temporarily unavailable for job %s", job_id)
            return []
        resp.raise_for_status()
        return TasksResponse.model_validate(resp.json()).tasks

    def submit_results(
        self,
        job_id: int,
        results: list[PipelineTaskResult],
        client_info: ProcessingServiceClientInfo | None = None,
    ) -> dict:
        """
        POST /jobs/{id}/result/ — deliver a list of PipelineTaskResult items.

        Antenna queues one Celery task per result for async processing.
        """
        body: dict = {"results": [r.model_dump(mode="json") for r in results]}
        if client_info is not None:
            body["client_info"] = client_info.model_dump(mode="json")
        resp = self.session.post(
            f"{self.api_url}/api/v2/jobs/{job_id}/result/",
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()
