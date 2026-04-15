"""
E2E tests for ami.jobs.tasks, focusing on error handling in process_nats_pipeline_result.

This test suite verifies the critical error handling path when PipelineResultsError
is received instead of successful pipeline results.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

from django.core.cache import cache
from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import Job, JobDispatchMode, JobState, MLJob
from ami.jobs.tasks import process_nats_pipeline_result
from ami.main.models import Detection, Project, SourceImage, SourceImageCollection
from ami.ml.models import Algorithm, Pipeline
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.orchestration.async_job_state import AsyncJobStateManager
from ami.ml.schemas import PipelineResultsError, PipelineResultsResponse, SourceImageResponse
from ami.users.models import User

logger = logging.getLogger(__name__)


class TestProcessNatsPipelineResultError(TransactionTestCase):
    """E2E tests for process_nats_pipeline_result with error handling."""

    def setUp(self):
        """Setup test fixtures."""
        cache.clear()  # Critical: clear Redis between tests

        self.project = Project.objects.create(name="Error Test Project")
        self.pipeline = Pipeline.objects.create(
            name="Test Pipeline",
            slug="test-pipeline",
        )
        self.pipeline.projects.add(self.project)

        self.collection = SourceImageCollection.objects.create(
            name="Test Collection",
            project=self.project,
        )

        self.job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Error Handling Job",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

        # Create test images
        self.images = [
            SourceImage.objects.create(
                path=f"test_image_{i}.jpg",
                public_base_url="http://example.com",
                project=self.project,
            )
            for i in range(3)
        ]

        # Initialize state manager
        self.image_ids = [str(img.pk) for img in self.images]
        self.state_manager = AsyncJobStateManager(self.job.pk)
        self.state_manager.initialize_job(self.image_ids)

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def _setup_mock_nats(self, mock_manager_class):
        """Helper to setup mock NATS manager."""
        mock_manager = AsyncMock()
        mock_manager.acknowledge_task = AsyncMock(return_value=True)
        mock_manager_class.return_value.__aenter__.return_value = mock_manager
        mock_manager_class.return_value.__aexit__.return_value = AsyncMock()
        return mock_manager

    def _create_error_result(self, image_id: str | None = None, error_msg: str = "Processing failed") -> dict:
        res_err = PipelineResultsError(
            error=error_msg,
            image_id=image_id,
        )
        return res_err.dict()

    def _assert_progress_updated(
        self, job_id: int, expected_processed: int, expected_total: int, stage: str = "process"
    ):
        """Assert TaskStateManager state is correct."""
        manager = AsyncJobStateManager(job_id)
        progress = manager.get_progress(stage)
        self.assertIsNotNone(progress, f"Progress not found for stage '{stage}'")
        self.assertEqual(progress.processed, expected_processed)
        self.assertEqual(progress.total, expected_total)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_process_nats_pipeline_result_with_error(self, mock_manager_class):
        """
        Test that PipelineResultsError is properly handled without saving to DB.
        """
        mock_manager = self._setup_mock_nats(mock_manager_class)

        # Create error result data for first image
        error_data = self._create_error_result(
            image_id=str(self.images[0].pk), error_msg="Failed to process image: invalid format"
        )
        reply_subject = "tasks.reply.test123"

        # Verify no detections exist before
        initial_detection_count = Detection.objects.count()

        # Execute task using .apply() for synchronous testing
        # This properly handles the bind=True decorator
        process_nats_pipeline_result.apply(
            kwargs={"job_id": self.job.pk, "result_data": error_data, "reply_subject": reply_subject}
        )

        # Assert: Progress was updated (1 of 3 images processed)
        self._assert_progress_updated(self.job.pk, expected_processed=1, expected_total=3, stage="process")
        self._assert_progress_updated(self.job.pk, expected_processed=1, expected_total=3, stage="results")

        # Assert: Job progress increased
        self.job.refresh_from_db()
        process_stage = next((s for s in self.job.progress.stages if s.key == "process"), None)
        self.assertIsNotNone(process_stage)
        self.assertGreater(process_stage.progress, 0)
        self.assertLess(process_stage.progress, 1.0)  # Not complete yet

        # Assert: Job status is still STARTED (not SUCCESS with incomplete stages)
        self.assertNotEqual(self.job.status, JobState.SUCCESS.value)

        # Assert: NO detections were saved to database
        self.assertEqual(Detection.objects.count(), initial_detection_count)

        mock_manager.acknowledge_task.assert_called_once_with(reply_subject)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_process_nats_pipeline_result_error_no_image_id(self, mock_manager_class):
        """
        Test error handling when image_id is None.

        This tests the fallback: processed_image_ids = set() when no image_id.
        """
        mock_manager = self._setup_mock_nats(mock_manager_class)

        # Create error result without image_id
        error_data = self._create_error_result(error_msg="General pipeline failure", image_id=None)
        reply_subject = "tasks.reply.test456"

        # Execute task using .apply()
        process_nats_pipeline_result.apply(
            kwargs={"job_id": self.job.pk, "result_data": error_data, "reply_subject": reply_subject}
        )

        # Assert: Progress was NOT updated (empty set of processed images)
        # Since no image_id was provided, processed_image_ids = set()
        manager = AsyncJobStateManager(self.job.pk)
        progress = manager.get_progress("process")
        self.assertEqual(progress.processed, 0)  # No images marked as processed

        mock_manager.acknowledge_task.assert_called_once_with(reply_subject)

        # Assert: No detections saved for this job's images
        detections_for_job = Detection.objects.filter(source_image__in=self.images)
        self.assertEqual(detections_for_job.count(), 0)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_process_nats_pipeline_result_mixed_results(self, mock_manager_class):
        """
        Test realistic scenario with some images succeeding and others failing.

        Simulates processing batch where:
        - Image 1: Error (PipelineResultsError)
        - Image 2: Success with detections
        - Image 3: Error (PipelineResultsError)
        """
        mock_manager = self._setup_mock_nats(mock_manager_class)

        # Create detection algorithm for the pipeline
        detection_algorithm = Algorithm.objects.create(
            name="test-detector",
            key="test-detector",
            task_type=AlgorithmTaskType.LOCALIZATION,
        )
        # Update pipeline to include detection algorithm
        self.pipeline.algorithms.add(detection_algorithm)

        # For this test, we just want to verify progress tracking works with mixed results
        # We'll skip checking final job completion status since that depends on all stages

        # Process error for image 1
        error_data_1 = self._create_error_result(image_id=str(self.images[0].pk), error_msg="Image 1 failed")
        process_nats_pipeline_result.apply(
            kwargs={"job_id": self.job.pk, "result_data": error_data_1, "reply_subject": "reply.1"}
        )

        # Process success for image 2 (simplified - just tracking progress without actual detections)
        success_data_2 = PipelineResultsResponse(
            pipeline="test-pipeline",
            algorithms={},
            total_time=1.5,
            source_images=[SourceImageResponse(id=str(self.images[1].pk), url="http://example.com/test_image_1.jpg")],
            detections=[],
            errors=None,
        ).dict()
        process_nats_pipeline_result.apply(
            kwargs={"job_id": self.job.pk, "result_data": success_data_2, "reply_subject": "reply.2"}
        )

        # Process error for image 3
        error_data_3 = self._create_error_result(image_id=str(self.images[2].pk), error_msg="Image 3 failed")
        process_nats_pipeline_result.apply(
            kwargs={"job_id": self.job.pk, "result_data": error_data_3, "reply_subject": "reply.3"}
        )

        # Assert: All 3 images marked as processed in TaskStateManager
        manager = AsyncJobStateManager(self.job.pk)
        process_progress = manager.get_progress("process")
        self.assertIsNotNone(process_progress)
        self.assertEqual(process_progress.processed, 3)
        self.assertEqual(process_progress.total, 3)
        self.assertEqual(process_progress.percentage, 1.0)

        results_progress = manager.get_progress("results")
        self.assertIsNotNone(results_progress)
        self.assertEqual(results_progress.processed, 3)
        self.assertEqual(results_progress.total, 3)
        self.assertEqual(results_progress.percentage, 1.0)

        # Assert: Job progress stages updated
        self.job.refresh_from_db()
        process_stage = next((s for s in self.job.progress.stages if s.key == "process"), None)
        results_stage = next((s for s in self.job.progress.stages if s.key == "results"), None)

        self.assertIsNotNone(process_stage, "Process stage not found in job progress")
        self.assertIsNotNone(results_stage, "Results stage not found in job progress")

        # Both should be at 100%
        self.assertEqual(process_stage.progress, 1.0)
        self.assertEqual(results_stage.progress, 1.0)

        # Assert: All tasks acknowledged
        self.assertEqual(mock_manager.acknowledge_task.call_count, 3)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_process_nats_pipeline_result_concurrent_updates(self, mock_manager_class):
        """
        Test that concurrent workers update state independently without contention.

        Without a lock, two workers processing different images can both call
        update_state and receive valid progress — no retry needed, no blocking.
        """
        mock_manager = self._setup_mock_nats(mock_manager_class)

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Worker 1 processes images[0]
            result_1 = executor.submit(
                process_nats_pipeline_result.apply,
                kwargs={
                    "job_id": self.job.pk,
                    "result_data": self._create_error_result(image_id=str(self.images[0].pk)),
                    "reply_subject": "reply.concurrent.1",
                },
            )

            # Worker 2 processes images[1] — no retry, no lock to wait for
            result_2 = executor.submit(
                process_nats_pipeline_result.apply,
                kwargs={
                    "job_id": self.job.pk,
                    "result_data": self._create_error_result(image_id=str(self.images[1].pk)),
                    "reply_subject": "reply.concurrent.2",
                },
            )

        self.assertTrue(result_1.result().successful())
        self.assertTrue(result_2.result().successful())

        # Both images should be marked as processed
        manager = AsyncJobStateManager(self.job.pk)
        progress = manager.get_progress("process")
        self.assertIsNotNone(progress)
        self.assertEqual(progress.processed, 2)
        self.assertEqual(progress.total, 3)
        self.assertEqual(mock_manager.acknowledge_task.call_count, 2)

    @patch("ami.jobs.tasks._fail_job")
    @patch("ami.jobs.tasks._ack_task_via_nats")
    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_transient_redis_error_does_not_fail_job_or_ack(self, mock_manager_class, mock_ack, mock_fail):
        """
        #1219: A transient RedisError during update_state must NOT flip the job
        to FAILURE and must NOT ack the NATS reply. Celery's autoretry_for is
        responsible for retrying; acking or failing prematurely is what caused
        the production incident.

        We invoke the task body directly (bypassing Celery's retry machinery)
        so we can assert the raw behavior: the exception propagates, _fail_job
        is not called, and the NATS ack helper is not called.
        """
        from redis.exceptions import RedisError

        self._setup_mock_nats(mock_manager_class)
        error_data = self._create_error_result(image_id=str(self.images[0].pk))

        with patch.object(AsyncJobStateManager, "update_state", side_effect=RedisError("reset by peer")):
            with self.assertRaises(RedisError):
                # Calling the task as a function runs its body once with no retry.
                process_nats_pipeline_result(
                    job_id=self.job.pk,
                    result_data=error_data,
                    reply_subject="reply.transient",
                )

        mock_fail.assert_not_called()
        mock_ack.assert_not_called()

    @patch("ami.jobs.tasks._fail_job")
    @patch("ami.jobs.tasks._ack_task_via_nats")
    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_genuinely_missing_state_acks_and_fails_job(self, mock_manager_class, mock_ack, mock_fail):
        """
        #1219 pairs with the transient case: when the job's total-images key
        is actually gone from Redis (cleanup race / expiry), the task should
        ack NATS (to stop redelivery) and fail the job — there's no state
        to reconcile against. This path is now the ONLY reason _fail_job is
        called from process_nats_pipeline_result's first call site.
        """
        self._setup_mock_nats(mock_manager_class)
        error_data = self._create_error_result(image_id=str(self.images[0].pk))

        # Wipe out the state that setUp's initialize_job created. Now
        # update_state will see total_raw=None and return None (genuine).
        self.state_manager.cleanup()

        process_nats_pipeline_result(
            job_id=self.job.pk,
            result_data=error_data,
            reply_subject="reply.missing",
        )

        mock_ack.assert_called_once()
        mock_fail.assert_called_once()
        # New, accurate message — no longer the misleading "Redis state missing"
        # that users saw in the UI for transient connection drops.
        args, _ = mock_fail.call_args
        self.assertIn("Job state keys not found in Redis", args[1])

    @patch("ami.jobs.tasks._ack_task_via_nats")
    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_ack_deferred_until_after_results_stage_srem(self, mock_manager_class, mock_ack):
        """
        Bug A regression: NATS ACK must NOT happen until after the results-stage
        SREM is durable in Redis. A worker crash between save_results and the
        results SREM would otherwise strand the image in pending_images:results
        with NATS already drained (no redelivery) — the job's results stage
        never reaches 100% and no code path reconciles it.

        This test simulates a crash on the results-stage SREM. Correct behavior:
        - process-stage SREM succeeded (called first, no crash)
        - save_results ran
        - results-stage SREM raised RedisError → exception propagates to Celery
        - ACK was NOT called (so NATS will redeliver after ack_wait)

        On buggy code (ACK before results SREM), mock_ack would be called before
        the raise, leaving the id stranded in Redis.
        """
        from redis.exceptions import RedisError

        self._setup_mock_nats(mock_manager_class)

        # save_results requires the pipeline to have at least one detection
        # algorithm. Attach a minimal one so we exercise the full save_results
        # path before hitting the results-stage SREM we're testing.
        detection_algorithm = Algorithm.objects.create(
            name="ack-ordering-detector",
            key="ack-ordering-detector",
            task_type=AlgorithmTaskType.LOCALIZATION,
        )
        self.pipeline.algorithms.add(detection_algorithm)

        # Use a success result (not an error) so save_results path runs fully.
        # An empty detections list keeps save_results cheap.
        success_data = PipelineResultsResponse(
            pipeline="test-pipeline",
            algorithms={},
            total_time=1.0,
            source_images=[SourceImageResponse(id=str(self.images[0].pk), url="http://example.com/test_image_0.jpg")],
            detections=[],
            errors=None,
        ).dict()

        real_update_state = AsyncJobStateManager.update_state

        def fail_on_results_stage(self, processed_image_ids, stage, failed_image_ids=None):
            if stage == "results":
                raise RedisError("connection reset on results SREM")
            return real_update_state(self, processed_image_ids, stage, failed_image_ids)

        with patch.object(AsyncJobStateManager, "update_state", fail_on_results_stage):
            with self.assertRaises(RedisError):
                process_nats_pipeline_result(
                    job_id=self.job.pk,
                    result_data=success_data,
                    reply_subject="reply.ack-ordering",
                )

        mock_ack.assert_not_called()

        # Process stage SREM ran and removed the id; results stage still holds it,
        # waiting for a successful retry or NATS redelivery.
        process_progress = AsyncJobStateManager(self.job.pk).get_progress("process")
        results_progress = AsyncJobStateManager(self.job.pk).get_progress("results")
        self.assertEqual(process_progress.processed, 1)
        self.assertEqual(results_progress.processed, 0)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_results_counter_does_not_inflate_on_replay(self, mock_manager_class):
        """
        Bug A companion (antenna#1232): _update_job_progress("results") accumulates
        detections/classifications/captures by reading existing values and adding
        new ones — not idempotent. On a NATS redelivery or Celery retry, the same
        batch can legitimately arrive twice. The fix gates accumulation on
        update_state's newly_removed (SREM's integer return, 0 on replay).

        Scenario: deliver the same result twice. Counters should reflect one
        batch, not two.
        """
        self._setup_mock_nats(mock_manager_class)

        detection_algorithm = Algorithm.objects.create(
            name="replay-detector",
            key="replay-detector",
            task_type=AlgorithmTaskType.LOCALIZATION,
        )
        self.pipeline.algorithms.add(detection_algorithm)

        # Empty-detections success keeps save_results cheap; the counter
        # accumulation still runs because captures_count = len(source_images) = 1.
        success_data = PipelineResultsResponse(
            pipeline="test-pipeline",
            algorithms={},
            total_time=1.0,
            source_images=[SourceImageResponse(id=str(self.images[0].pk), url="http://example.com/test_image_0.jpg")],
            detections=[],
            errors=None,
        ).dict()

        # First delivery: counters should advance by 1 capture.
        process_nats_pipeline_result.apply(
            kwargs={"job_id": self.job.pk, "result_data": success_data, "reply_subject": "reply.first"}
        )

        self.job.refresh_from_db()
        results_stage = next(s for s in self.job.progress.stages if s.key == "results")
        captures_after_first = next(
            (p.value for p in results_stage.params if p.key == "captures"),
            0,
        )
        self.assertEqual(captures_after_first, 1, "first delivery should count 1 capture")

        # Second delivery of the same result (NATS redeliver / Celery retry after
        # the results SREM was already durable). SREM now returns 0 (id already
        # gone). Counters must NOT double.
        process_nats_pipeline_result.apply(
            kwargs={"job_id": self.job.pk, "result_data": success_data, "reply_subject": "reply.replay"}
        )

        self.job.refresh_from_db()
        results_stage = next(s for s in self.job.progress.stages if s.key == "results")
        captures_after_replay = next(
            (p.value for p in results_stage.params if p.key == "captures"),
            0,
        )
        self.assertEqual(
            captures_after_replay,
            1,
            f"replay must not inflate captures counter (got {captures_after_replay}, expected 1)",
        )

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_process_nats_pipeline_result_error_job_not_found(self, mock_manager_class):
        """
        Test graceful handling when job is deleted before error processed.

        From tasks.py lines 97-101, should log error and acknowledge without raising.
        """
        mock_manager = self._setup_mock_nats(mock_manager_class)

        # Create error result
        error_data = self._create_error_result(image_id=str(self.images[0].pk))
        reply_subject = "tasks.reply.test999"

        # Delete the job
        deleted_job_id = self.job.pk
        self.job.delete()

        # Should NOT raise exception - task should handle gracefully
        process_nats_pipeline_result.apply(
            kwargs={
                "job_id": deleted_job_id,
                "result_data": error_data,
                "reply_subject": reply_subject,
            }
        )

        # Assert: Task was acknowledged despite missing job
        mock_manager.acknowledge_task.assert_called_once_with(reply_subject)


class TestResultEndpointWithError(APITestCase):
    """Integration test for the result API endpoint with error results."""

    def setUp(self):
        """Setup test fixtures."""
        cache.clear()

        self.user = User.objects.create_user(  # type: ignore
            email="testuser-error@insectai.org",
            is_staff=True,
            is_active=True,
            is_superuser=True,
        )

        self.project = Project.objects.create(name="Error API Test Project")
        self.pipeline = Pipeline.objects.create(
            name="Test Pipeline for Errors",
            slug="test-error-pipeline",
        )
        self.pipeline.projects.add(self.project)

        self.collection = SourceImageCollection.objects.create(
            name="Test Collection",
            project=self.project,
        )

        self.job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="API Test Error Job",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

        self.image = SourceImage.objects.create(
            path="test_error_image.jpg",
            public_base_url="http://example.com",
            project=self.project,
        )

        # Initialize state manager
        state_manager = AsyncJobStateManager(self.job.pk)
        state_manager.initialize_job([str(self.image.pk)])

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @patch("ami.jobs.tasks.process_nats_pipeline_result.apply_async")
    def test_result_endpoint_with_error_result(self, mock_apply_async):
        """
        E2E test through the API endpoint that queues the task.

        Tests the full flow: API -> Celery task -> Error handling
        """
        # Configure mock to return a proper task-like object with serializable id

        mock_result = MagicMock()
        mock_result.id = "test-task-id-123"
        mock_apply_async.return_value = mock_result

        self.client.force_authenticate(user=self.user)
        result_url = reverse_with_params("api:job-result", args=[self.job.pk], params={"project_id": self.project.pk})

        # Create error result data (wrapped format)
        result_data = {
            "results": [
                {
                    "reply_subject": "test.reply.error.1",
                    "result": {
                        "error": "Image processing timeout",
                        "image_id": str(self.image.pk),
                    },
                }
            ]
        }

        # POST error result to API
        resp = self.client.post(result_url, result_data, format="json")

        # Assert: API accepted the error result
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["job_id"], self.job.pk)
        self.assertEqual(data["results_queued"], 1)
        self.assertEqual(len(data["tasks"]), 1)
        self.assertEqual(data["tasks"][0]["task_id"], "test-task-id-123")
        self.assertEqual(data["tasks"][0]["status"], "queued")

        # Assert: Celery task was queued
        mock_apply_async.assert_called_once()

        # Verify the task was called with correct arguments.
        # NOTE on Celery calling convention:
        # .delay(k1=v1, k2=v2) calls .apply_async((), {k1: v1, k2: v2})
        # i.e. two *positional* args to apply_async: an empty args tuple and a kwargs dict.
        # This is NOT the same as apply_async(kwargs={...}) which uses a keyword argument.
        # So mock.call_args[0] == ((), {task kwargs}) — a 2-element tuple.
        call_args = mock_apply_async.call_args[0]
        self.assertEqual(len(call_args), 2, "apply_async should be called with (args, kwargs)")
        task_kwargs = call_args[1]  # Second positional arg is the kwargs dict
        self.assertEqual(task_kwargs["job_id"], self.job.pk)
        self.assertEqual(task_kwargs["reply_subject"], "test.reply.error.1")
        self.assertIn("error", task_kwargs["result_data"])
