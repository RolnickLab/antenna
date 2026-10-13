"""Tests for the pull-mode worker against a fake Antenna. Run with: python -m unittest worker.test_worker"""

import os
import unittest
from unittest import mock

import PIL.Image
from api.api import pipeline_choices

from .client import AntennaClient
from .loop import Loop
from .runner import process_task
from .schemas import PipelineProcessingTask, PipelineResultsError, ProcessingServiceClientInfo

WORKER_ENV = {"WORKER_POLL_INTERVAL_SECONDS": "0", "WORKER_BATCH_SIZE": "2"}


def task(image_id: str = "7") -> PipelineProcessingTask:
    return PipelineProcessingTask(
        id=f"task-{image_id}", image_id=image_id, image_url=f"http://example.com/{image_id}.jpg", reply_subject="r"
    )


class FakeClient:
    """Lists the given jobs once, hands out one task per job, and records the submitted results."""

    def __init__(self, jobs: list[tuple[int, str]]):
        self.jobs = jobs
        self.listed_slugs: list[str] = []
        self.submitted: dict[int, list] = {}

    def list_active_jobs(self, pipeline_slugs):
        self.listed_slugs = pipeline_slugs
        jobs, self.jobs = self.jobs, []
        return jobs

    def reserve_tasks(self, job_id, batch_size, client_info=None):
        return [task(str(job_id))]

    def submit_results(self, job_id, results, client_info=None):
        self.submitted[job_id] = results
        return {"results_queued": len(results)}


class WorkerTestCase(unittest.TestCase):
    def setUp(self):
        for patcher in (
            mock.patch("api.schemas.get_image", return_value=PIL.Image.new("RGB", (640, 480))),
            mock.patch.dict(os.environ, WORKER_ENV),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)


class TestLoop(WorkerTestCase):
    def run_once(self, client: FakeClient) -> bool:
        return Loop(client, ProcessingServiceClientInfo())._iterate()  # type: ignore[arg-type]

    def test_each_job_is_processed_with_its_own_pipeline(self):
        client = FakeClient([(1, "constant"), (2, "random-detection-random-species")])
        self.assertTrue(self.run_once(client))
        self.assertEqual(client.listed_slugs, list(pipeline_choices))
        for job_id, slug in ((1, "constant"), (2, "random-detection-random-species")):
            [result] = client.submitted[job_id]
            self.assertEqual(result.reply_subject, "r")
            self.assertEqual(result.result.pipeline, slug)
            # Antenna counts an image as processed only when it appears in source_images.
            self.assertEqual([image.id for image in result.result.source_images], [str(job_id)])

    def test_a_job_for_a_pipeline_the_worker_does_not_offer_is_skipped(self):
        client = FakeClient([(3, "not-offered")])
        self.assertFalse(self.run_once(client))
        self.assertEqual(client.submitted, {})


class TestRunner(WorkerTestCase):
    def test_an_unopenable_image_becomes_an_error_result_for_that_image(self):
        with mock.patch("api.schemas.get_image", return_value=None):
            result = process_task(task(), "constant").result
        self.assertIsInstance(result, PipelineResultsError)
        self.assertEqual(result.image_id, "7")


class TestClient(unittest.TestCase):
    def test_lists_jobs_with_the_query_antenna_uses_as_the_worker_heartbeat(self):
        client = AntennaClient("http://antenna", "Token x")
        response = mock.Mock(json=lambda: {"count": 1, "results": [{"id": 5, "pipeline_slug": "constant"}]})
        with mock.patch.object(client.session, "get", return_value=response) as get:
            self.assertEqual(client.list_active_jobs(["constant", "random"]), [(5, "constant")])
        self.assertEqual(
            get.call_args.kwargs["params"],
            {
                "pipeline__slug__in": "constant,random",
                "ids_only": 1,
                "incomplete_only": 1,
                "dispatch_mode": "async_api",
            },
        )
