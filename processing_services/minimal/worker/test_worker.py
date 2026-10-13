"""Tests for the pull-mode worker against a fake Antenna. Run with: python -m unittest worker.test_worker"""

import os
import unittest
from unittest import mock

import PIL.Image
from api import algorithms
from api.api import worker_pipelines

from .client import AntennaClient
from .loop import Loop
from .runner import check_worker_settings, process_task, worker_request_config
from .schemas import PipelineProcessingTask, PipelineResultsError, ProcessingServiceClientInfo

WORKER_ENV = {"WORKER_POLL_INTERVAL_SECONDS": "0", "WORKER_BATCH_SIZE": "2"}


def task(image_id: str = "7") -> PipelineProcessingTask:
    return PipelineProcessingTask(
        id=f"task-{image_id}", image_id=image_id, image_url=f"http://example.com/{image_id}.jpg", reply_subject="r"
    )


class FakeClient:
    """Lists the given jobs once, hands out one batch of tasks per job, and records submitted results."""

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
        patchers = [
            mock.patch("api.schemas.get_image", return_value=PIL.Image.new("RGB", (640, 480))),
            mock.patch.dict(os.environ, WORKER_ENV),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_loop_once(self, client: FakeClient) -> bool:
        return Loop(client, ProcessingServiceClientInfo())._iterate()  # type: ignore[arg-type]


class TestLoop(WorkerTestCase):
    def test_feature_only_pipelines_are_not_offered_in_pull_mode(self):
        slugs = {pipeline.config.slug for pipeline in worker_pipelines}
        self.assertIn("constant-with-feature-extractor", slugs)
        self.assertNotIn("constant-feature-extractor-only", slugs)

    def test_results_for_each_job_come_from_that_jobs_pipeline_and_carry_vectors(self):
        client = FakeClient([(1, "constant-with-feature-extractor"), (2, "constant")])
        self.assertTrue(self.run_loop_once(client))
        self.assertEqual(client.listed_slugs, [pipeline.config.slug for pipeline in worker_pipelines])

        [with_vectors] = client.submitted[1]
        self.assertEqual(with_vectors.reply_subject, "r")
        self.assertEqual(with_vectors.result.pipeline, "constant-with-feature-extractor")
        [detection] = with_vectors.result.detections
        [embedding] = detection.embeddings
        self.assertEqual(embedding.algorithm.key, algorithms.CONSTANT_FEATURE_EXTRACTOR.key)

        [without_vectors] = client.submitted[2]
        self.assertIsNone(without_vectors.result.detections[0].embeddings)

    def test_a_job_for_a_pipeline_the_worker_does_not_offer_is_skipped(self):
        client = FakeClient([(3, "constant-feature-extractor-only")])
        self.assertFalse(self.run_loop_once(client))
        self.assertEqual(client.submitted, {})


class TestRunner(WorkerTestCase):
    def test_env_settings_apply_to_pull_mode_tasks(self):
        env = {"AMI_EMBEDDING_EXTRACTOR": "", "AMI_FEATURES_FOR_ALL_DETECTIONS": "true", "AMI_INCLUDE_LOGITS": "0"}
        with mock.patch.dict(os.environ, env):
            config = worker_request_config()
            result = process_task(task(), "constant-with-feature-extractor").result
        self.assertEqual(config.embedding_extractor, "")
        [detection] = result.detections
        [embedding] = detection.embeddings
        self.assertEqual(embedding.algorithm.key, algorithms.CONSTANT_CLASSIFIER.key)

    def test_an_extractor_setting_does_not_fail_pipelines_without_an_extractor(self):
        with mock.patch.dict(os.environ, {"AMI_EMBEDDING_EXTRACTOR": "constant-feature-extractor"}):
            check_worker_settings()
            result = process_task(task(), "constant").result
        self.assertNotIsInstance(result, PipelineResultsError)

    def test_an_unknown_extractor_setting_stops_the_worker_at_startup(self):
        with mock.patch.dict(os.environ, {"AMI_EMBEDDING_EXTRACTOR": "typo"}):
            with self.assertRaises(ValueError):
                check_worker_settings()

    def test_a_worker_with_no_pull_mode_pipelines_stops_at_startup(self):
        with mock.patch("worker.runner.worker_pipelines", []):
            with self.assertRaises(RuntimeError):
                check_worker_settings()

    def test_an_unopenable_image_becomes_an_error_result(self):
        with mock.patch("api.schemas.get_image", return_value=None):
            result = process_task(task(), "constant").result
        self.assertIsInstance(result, PipelineResultsError)
        self.assertEqual(result.image_id, "7")


class TestClient(unittest.TestCase):
    def test_lists_jobs_with_the_same_query_as_the_data_companion_worker(self):
        client = AntennaClient("http://antenna", "Token x")
        response = mock.Mock(json=lambda: {"results": [{"id": 5, "pipeline_slug": "constant"}]})
        with mock.patch.object(client.session, "get", return_value=response) as get:
            self.assertEqual(client.list_active_jobs(["constant", "random"]), [(5, "constant")])
        params = get.call_args.kwargs["params"]
        self.assertEqual(
            params,
            {
                "pipeline__slug__in": "constant,random",
                "ids_only": 1,
                "incomplete_only": 1,
                "dispatch_mode": "async_api",
            },
        )
