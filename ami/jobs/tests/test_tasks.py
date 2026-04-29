"""
E2E tests for ami.jobs.tasks, focusing on error handling in process_nats_pipeline_result.

This test suite verifies the critical error handling path when PipelineResultsError
is received instead of successful pipeline results.
"""

import datetime
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
        # Reason string now leads with the stage and embeds a live Redis
        # snapshot (DB index + key listing from diagnose_missing_state) so the
        # failure cause — DB-index drift, eviction, or never-initialized —
        # is visible in the FAILURE log instead of the previous single
        # hardcoded "likely cleaned up concurrently" guess.
        args, _ = mock_fail.call_args
        self.assertIn("Job state missing from Redis", args[1])
        self.assertIn("stage=process", args[1])

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


class TestTaskFailureGuard(TransactionTestCase):
    """
    Bug C regression tests for the task_failure signal guard in update_job_failure.

    Pre-PR-#1234 behavior: any exception raised in run_job (even after the images
    were successfully queued to NATS and ADC workers were processing them) flowed
    through Celery's task_failure signal and collapsed the job: status → FAILURE
    and NATS/Redis cleanup destroyed state the result handler depended on.

    Post-PR-#1234 behavior: for ASYNC_API jobs that aren't progress.is_complete()
    yet, the guard defers terminal state to the async result handler. Non-ASYNC
    dispatch modes (and ASYNC_API jobs that have actually completed) still take
    the terminal path.

    Tests here call `update_job_failure` as a plain function with the positional
    arguments the task_failure signal would pass at runtime. The Celery signal
    machinery itself is not the subject of the test — the signal handler body is.
    """

    def setUp(self):
        cache.clear()
        self.project = Project.objects.create(name="Bug C Guard Test Project")
        self.pipeline = Pipeline.objects.create(name="Bug C Pipeline", slug="bug-c-pipeline")
        self.pipeline.projects.add(self.project)
        self.collection = SourceImageCollection.objects.create(name="Bug C Collection", project=self.project)

    def tearDown(self):
        cache.clear()

    def _make_job(self, dispatch_mode: JobDispatchMode, task_id: str) -> Job:
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name=f"{dispatch_mode} bug C test job",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=dispatch_mode,
        )
        job.task_id = task_id
        # Initial status mirrors what run_job has already set via task_prerun by
        # the time task_failure fires.
        job.update_status(JobState.STARTED, save=True)
        return job

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_task_failure_guard_defers_for_async_api_in_flight(self, mock_cleanup):
        """
        Bug C: an exception in run_job post-queue on an ASYNC_API job must NOT
        flip the job to FAILURE or fire cleanup — results are still arriving
        via NATS, and tearing down stream/consumer/Redis state now would strand
        the in-flight images. The guard at tasks.py:729 handles this.
        """
        from ami.jobs.tasks import update_job_failure

        job = self._make_job(JobDispatchMode.ASYNC_API, task_id="bug-c-async-task")
        # Initialize Redis state so progress.is_complete() is False (there are
        # pending images). Also stand in for the ADC worker's view: it would
        # still see state here and keep publishing results.
        image_ids = ["100", "101", "102"]
        AsyncJobStateManager(job.pk).initialize_job(image_ids)

        with self.assertLogs("ami.jobs", level="WARNING") as captured:
            update_job_failure(
                sender=None,
                task_id=job.task_id,
                exception=RuntimeError("simulated post-queue crash"),
            )

        job.refresh_from_db()

        # Job status unchanged: the guard returned before update_status(FAILURE).
        self.assertEqual(
            job.status,
            JobState.STARTED,
            "ASYNC_API in-flight job should remain STARTED when run_job raises",
        )
        # Cleanup deferred: state is still needed by the async result handler.
        mock_cleanup.assert_not_called()
        # Redis state untouched — the NATS worker can keep reporting against it.
        surviving_progress = AsyncJobStateManager(job.pk).get_progress("results")
        self.assertIsNotNone(surviving_progress)
        self.assertEqual(surviving_progress.remaining, len(image_ids))
        # Warning log surfaces the deferred failure. Ops alerting on this phrase
        # is how the visibility loss described in the PR body is compensated.
        self.assertTrue(
            any("deferring FAILURE to async progress handler" in line for line in captured.output),
            f"expected deferral warning, got: {captured.output}",
        )

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_task_failure_marks_sync_api_job_failure_and_cleans_up(self, mock_cleanup):
        """
        Contract pair for the ASYNC_API guard: SYNC_API (and INTERNAL) jobs have
        no in-flight external processing to preserve, so task_failure must still
        mark FAILURE and invoke cleanup as before.
        """
        from ami.jobs.tasks import update_job_failure

        job = self._make_job(JobDispatchMode.SYNC_API, task_id="bug-c-sync-task")

        update_job_failure(
            sender=None,
            task_id=job.task_id,
            exception=RuntimeError("sync api crash"),
        )

        job.refresh_from_db()

        self.assertEqual(job.status, JobState.FAILURE)
        mock_cleanup.assert_called_once()


class TestFailJob(TransactionTestCase):
    """
    Regression tests for ``_fail_job`` — specifically for the reason-string
    mirroring into ``progress.errors`` that this PR adds.

    The FAILURE log line alone is not enough for operators; the UI reads
    ``progress.errors``, and prior to this PR that list stayed empty on the
    missing-Redis-state path. Any regression that stops appending the reason
    (e.g. silently dropping it via the defensive ``try/except``) would put
    operators back in the position of digging through Celery worker logs to
    find out why a job died.
    """

    def setUp(self):
        cache.clear()
        self.project = Project.objects.create(name="FailJob Test Project")
        self.pipeline = Pipeline.objects.create(name="FailJob Pipeline", slug="fail-job-pipeline")
        self.pipeline.projects.add(self.project)
        self.collection = SourceImageCollection.objects.create(name="FailJob Collection", project=self.project)

    def tearDown(self):
        cache.clear()

    def _make_job(self, dispatch_mode: JobDispatchMode = JobDispatchMode.ASYNC_API) -> Job:
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name=f"{dispatch_mode} fail-job test",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=dispatch_mode,
        )
        job.update_status(JobState.STARTED, save=True)
        return job

    @patch("ami.ml.orchestration.jobs.cleanup_async_job_resources")
    def test_fail_job_appends_reason_to_progress_errors(self, mock_cleanup):
        """
        Reason string must end up in ``job.progress.errors`` (persisted) so the
        UI shows the cause of the FAILURE alongside the status change. Before
        this PR the reason lived only in ``job.logger`` and the UI showed
        ``errors=[]``. A silent regression here would not be caught by the
        ``_fail_job`` call-site tests in ``TestProcessNatsPipelineResultError``
        (they mock ``_fail_job`` entirely).
        """
        from ami.jobs.tasks import _fail_job

        job = self._make_job()
        reason = "Job state missing from Redis (stage=process): redis=host:6379/db1 keys_for_job=<none>"

        _fail_job(job.pk, reason)

        job.refresh_from_db()
        self.assertEqual(job.status, JobState.FAILURE)
        self.assertIn(
            reason,
            job.progress.errors,
            f"expected reason in progress.errors, got: {job.progress.errors!r}",
        )
        # Sanity: the fix also propagates to the DB-persisted copy (i.e. the
        # update_fields tuple on job.save includes 'progress'). Re-read from a
        # fresh Job instance to prove the append wasn't only visible on the
        # in-memory object returned by select_for_update.
        reloaded = Job.objects.get(pk=job.pk)
        self.assertIn(reason, reloaded.progress.errors)
        mock_cleanup.assert_called_once_with(job.pk)

    @patch("ami.ml.orchestration.jobs.cleanup_async_job_resources")
    def test_fail_job_is_noop_on_already_final_job(self, mock_cleanup):
        """
        If the job is already in a final state (e.g. concurrent cleanup
        beat us), ``_fail_job`` must return early without touching status
        or progress. This protects against double-failing a job that has
        already been reconciled to SUCCESS by the reconciler path.
        """
        from ami.jobs.tasks import _fail_job

        job = self._make_job()
        job.update_status(JobState.SUCCESS, save=True)
        errors_before = list(job.progress.errors)

        _fail_job(job.pk, "should be ignored")

        job.refresh_from_db()
        self.assertEqual(job.status, JobState.SUCCESS)
        self.assertEqual(job.progress.errors, errors_before)
        mock_cleanup.assert_not_called()


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


class TestLogWorkerAvailability(TransactionTestCase):
    """Verify the worker-availability log lines emitted when run_job hands an
    async_api job off to NATS. These replace the previous opaque
    "async results still in-flight" line with a concrete count of how many
    workers are actually online for the job's pipeline, plus a WARNING when
    nothing has been heard from a worker in the last hour (the strong signal
    that the job will stall indefinitely)."""

    def setUp(self):
        cache.clear()
        self.project = Project.objects.create(name="Worker Availability Test")
        self.pipeline = Pipeline.objects.create(name="Test Pipeline", slug="test_pipeline")
        self.pipeline.projects.add(self.project)
        self.collection = SourceImageCollection.objects.create(name="WA Collection", project=self.project)
        self.job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="WA Test Job",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

    def tearDown(self):
        cache.clear()

    def _make_service(self, name: str, last_seen_offset_seconds: int | None, live: bool):
        """Create a ProcessingService attached to self.pipeline.

        ``last_seen_offset_seconds=None`` leaves last_seen unset (never seen).
        Positive offset sets last_seen in the past by that many seconds.
        """
        import datetime as _dt

        from ami.ml.models.processing_service import ProcessingService

        svc = ProcessingService.objects.create(name=name, endpoint_url=None)
        svc.pipelines.add(self.pipeline)
        svc.projects.add(self.project)
        if last_seen_offset_seconds is not None:
            svc.last_seen = _dt.datetime.now() - _dt.timedelta(seconds=last_seen_offset_seconds)
        svc.last_seen_live = live
        svc.save(update_fields=["last_seen", "last_seen_live"])
        return svc

    def _run_and_capture(self):
        """Call _log_worker_availability(self.job) and return captured.output (a flat list
        of "LEVEL:logger:message" strings) from the per-job logger.

        Uses the specific per-job logger name (f"ami.jobs.{job.pk}") because that logger
        has propagate=False, so assertLogs("ami.jobs", ...) would catch nothing.
        """
        from ami.jobs.tasks import _log_worker_availability

        with self.assertLogs(f"ami.jobs.{self.job.pk}", level="INFO") as captured:
            _log_worker_availability(self.job)
        return captured.output

    def test_no_workers_emits_info_and_warning(self):
        """Zero configured services: '0/0 online recently' + WARNING."""
        output = self._run_and_capture()
        info_line = next((ln for ln in output if "Waiting for workers" in ln), None)
        self.assertIsNotNone(info_line, f"missing info line in {output}")
        self.assertIn("'test_pipeline'", info_line)
        self.assertIn("(0/0 online recently)", info_line)
        warn_line = next((ln for ln in output if "Zero workers have been seen" in ln), None)
        self.assertIsNotNone(warn_line, f"missing warning line in {output}")
        self.assertIn("WARNING", warn_line)
        self.assertIn("'test_pipeline'", warn_line)
        self.assertIn("in the last hour", warn_line)

    def test_one_worker_live_and_recent_no_warning(self):
        """A service seen 10s ago and live: '1/1 online recently', no WARNING."""
        self._make_service("fresh-worker", last_seen_offset_seconds=10, live=True)
        output = self._run_and_capture()
        info_line = next((ln for ln in output if "Waiting for workers" in ln), None)
        self.assertIsNotNone(info_line)
        self.assertIn("(1/1 online recently)", info_line)
        self.assertFalse(
            any("Zero workers have been seen" in ln for ln in output),
            f"unexpected warning in {output}",
        )

    def test_mixed_services_correct_count(self):
        """One live+recent, one live-but-stale, one seen-in-hour, one never-seen:
        online=1/4, no WARNING (someone has been seen in the last hour)."""
        self._make_service("fresh-live", last_seen_offset_seconds=10, live=True)
        self._make_service("stale-live", last_seen_offset_seconds=600, live=True)  # 10 min ago
        self._make_service("recent-dead", last_seen_offset_seconds=600, live=False)
        self._make_service("never-seen", last_seen_offset_seconds=None, live=False)
        output = self._run_and_capture()
        info_line = next((ln for ln in output if "Waiting for workers" in ln), None)
        self.assertIsNotNone(info_line)
        self.assertIn("(1/4 online recently)", info_line)
        self.assertFalse(any("Zero workers have been seen" in ln for ln in output))

    def test_all_services_stale_beyond_hour_emits_warning(self):
        """Two services, both last seen > 1h ago: '0/2 online recently' + WARNING."""
        self._make_service("old-1", last_seen_offset_seconds=7200, live=False)  # 2h ago
        self._make_service("old-2", last_seen_offset_seconds=3700, live=False)  # just over 1h
        output = self._run_and_capture()
        info_line = next((ln for ln in output if "Waiting for workers" in ln), None)
        self.assertIsNotNone(info_line)
        self.assertIn("(0/2 online recently)", info_line)
        self.assertTrue(any("Zero workers have been seen" in ln for ln in output))

    def test_service_seen_within_hour_but_not_recent_no_warning(self):
        """Service seen 30 min ago (not 'online recently' but within the hour):
        '0/1 online recently', no WARNING — the soft-hour signal is what gates it."""
        self._make_service("half-hour-old", last_seen_offset_seconds=1800, live=False)
        output = self._run_and_capture()
        info_line = next((ln for ln in output if "Waiting for workers" in ln), None)
        self.assertIsNotNone(info_line)
        self.assertIn("(0/1 online recently)", info_line)
        self.assertFalse(any("Zero workers have been seen" in ln for ln in output))

    def test_job_with_no_pipeline_logs_generic_message(self):
        """Pipeline-less job: a generic waiting line, no pipeline-specific warning."""
        self.job.pipeline = None
        self.job.save(update_fields=["pipeline"])
        output = self._run_and_capture()
        self.assertTrue(
            any("Waiting for workers to pick up tasks" in ln and "no pipeline assigned" in ln for ln in output),
            f"expected generic no-pipeline line in {output}",
        )
        self.assertFalse(any("Zero workers have been seen" in ln for ln in output))


class TestMarkLostImagesFailed(TransactionTestCase):
    """Regression tests for the NATS-lost-images reconciler.

    Production incident 2026-04-16 (job 2421): 998 images, 982 processed cleanly,
    5 explicit failures, and 16 images stuck indefinitely in Redis pending_images
    after an ADC worker hit a 2h NATS/Redis connection drop. NATS had given up
    (max_deliver=2) before the worker reconnected, so the messages were gone
    but the job kept sitting at 98.4% until ``check_stale_jobs`` REVOKED it and
    discarded the 98% of successful work.

    The right outcome for that job was SUCCESS with ``failed=21/998`` (~2%), not
    REVOKED. This test shape mirrors the incident: successful SREMs, explicit
    failures already in ``failed_images``, and a residual "lost" set still in
    both pending_images:{process,results}. The helper under test should SADD the
    lost ids to ``failed_images``, SREM them from the pending sets, and let the
    existing completion logic in ``_update_job_progress`` finalize the job.
    """

    def setUp(self):
        cache.clear()
        self.project = Project.objects.create(name="Lost Images Test Project")
        self.pipeline = Pipeline.objects.create(name="Lost Pipeline", slug="lost-pipeline")
        self.pipeline.projects.add(self.project)
        self.collection = SourceImageCollection.objects.create(name="Lost Coll", project=self.project)

    def tearDown(self):
        cache.clear()

    def _make_stuck_job(self, total_images: int = 10, already_processed: int = 7, explicit_failures: int = 1):
        """Build the job-2421 Redis + Job.progress shape.

        Returns (job, set_of_lost_ids). The lost count is derived so the three
        buckets always sum to ``total_images``.
        """
        lost = total_images - already_processed - explicit_failures
        assert lost > 0, "test requires at least one lost image"

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="job-2421-shape",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )
        all_ids = [str(i) for i in range(1000, 1000 + total_images)]
        processed_ids = set(all_ids[:already_processed])
        failed_ids = set(all_ids[already_processed : already_processed + explicit_failures])
        lost_ids = set(all_ids[already_processed + explicit_failures :])

        manager = AsyncJobStateManager(job.pk)
        manager.initialize_job(all_ids)
        # Successful results for the first bucket: SREM from both pending sets.
        manager.update_state(processed_ids, stage="process")
        manager.update_state(processed_ids, stage="results")
        # Explicit failures: SREM from both pending sets + SADD to failed_images
        # (mirrors what process_nats_pipeline_result does with a PipelineResultsError).
        manager.update_state(failed_ids, stage="process", failed_image_ids=failed_ids)
        manager.update_state(failed_ids, stage="results")

        # Mirror the last _update_job_progress snapshot into job.progress.
        progress = job.progress
        collect_stage = progress.get_stage("collect")
        collect_stage.progress = 1.0
        collect_stage.status = JobState.SUCCESS
        non_lost = already_processed + explicit_failures
        progress.update_stage(
            "process",
            progress=non_lost / total_images,
            status=JobState.STARTED,
            processed=non_lost,
            remaining=lost,
            failed=explicit_failures,
        )
        progress.update_stage(
            "results",
            progress=non_lost / total_images,
            status=JobState.STARTED,
            detections=0,
            classifications=0,
            captures=already_processed,
        )
        job.status = JobState.STARTED
        job.save()

        # Force updated_at to appear stale so the helper considers this job.
        Job.objects.filter(pk=job.pk).update(
            updated_at=datetime.datetime.now() - datetime.timedelta(minutes=Job.STALLED_JOBS_MAX_MINUTES + 1)
        )
        job.refresh_from_db()
        return job, lost_ids

    def _mock_consumer_state(
        self,
        mock_manager_class,
        num_pending: int = 0,
        num_ack_pending: int = 0,
        num_redelivered: int = 0,
    ):
        from ami.ml.orchestration.nats_queue import ConsumerState

        mock_manager = AsyncMock()
        mock_manager.get_consumer_state = AsyncMock(
            return_value=ConsumerState(
                num_pending=num_pending,
                num_ack_pending=num_ack_pending,
                num_redelivered=num_redelivered,
            )
        )
        mock_manager_class.return_value.__aenter__.return_value = mock_manager
        mock_manager_class.return_value.__aexit__.return_value = AsyncMock()
        return mock_manager

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_marks_lost_images_as_failed_and_finalizes_success(self, mock_manager_class):
        """Job-2421 shape: NATS drained (num_pending=0, num_ack_pending=0) while
        Redis pending still holds redelivery-exhausted ids. The helper should
        SADD those to failed_images, SREM from pending, and let the existing
        completion logic (failed/total < FAILURE_THRESHOLD) land the job in SUCCESS.
        """
        from ami.jobs.tasks import mark_lost_images_failed

        job, lost_ids = self._make_stuck_job(total_images=10, already_processed=7, explicit_failures=1)
        self._mock_consumer_state(mock_manager_class, num_pending=0, num_ack_pending=0, num_redelivered=len(lost_ids))

        results = mark_lost_images_failed()

        self.assertEqual(len(results), 1, f"expected one job reconciled, got {results}")
        self.assertEqual(results[0]["job_id"], job.pk)
        self.assertEqual(results[0]["lost_count"], len(lost_ids))
        self.assertEqual(results[0]["action"], "marked_failed")

        job.refresh_from_db()
        self.assertEqual(
            job.status,
            JobState.SUCCESS.value,
            f"expected SUCCESS (failed=3/10 below FAILURE_THRESHOLD); got {job.status}",
        )
        self.assertTrue(job.progress.is_complete(), f"stages not complete: {job.progress.stages}")

        process = job.progress.get_stage("process")
        self.assertEqual(process.progress, 1.0)
        failed_param = next((p.value for p in process.params if p.key == "failed"), None)
        self.assertEqual(
            failed_param,
            3,
            f"process.failed should be explicit_failures (1) + lost (2) = 3, got {failed_param}",
        )
        remaining_param = next((p.value for p in process.params if p.key == "remaining"), None)
        self.assertEqual(remaining_param, 0, f"process.remaining should be 0, got {remaining_param}")

        # Redis state is wiped by cleanup_async_job_if_needed once is_complete()
        # fires, so we assert against the durable Job.progress snapshot, not
        # AsyncJobStateManager.get_progress (which returns None after cleanup).

        self.assertTrue(
            any("job idle past cutoff" in e for e in job.progress.errors),
            f"expected diagnostic in progress.errors, got {job.progress.errors}",
        )

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_reconciles_when_consumer_shows_undelivered_pending(self, mock_manager_class):
        """Idle cutoff is the decision signal, not NATS counters. A job with
        ``updated_at`` >10 min old and ``num_pending > 0`` means ADC hasn't
        pulled messages for >10 min; those images are stuck regardless of what
        the NATS stream looks like. Reconcile."""
        from ami.jobs.tasks import mark_lost_images_failed

        job, lost_ids = self._make_stuck_job()
        self._mock_consumer_state(mock_manager_class, num_pending=len(lost_ids), num_ack_pending=0, num_redelivered=0)

        results = mark_lost_images_failed()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "marked_failed")
        job.refresh_from_db()
        self.assertTrue(job.progress.is_complete())

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_reconciles_when_consumer_shows_ack_pending(self, mock_manager_class):
        """Empirical NATS behavior: after ``max_deliver`` exhaustion, messages
        stay in ``num_ack_pending`` indefinitely (not cleared until stream
        deletion). This is the exact production failure mode — guarding on
        ``num_ack_pending > 0`` would block recovery from the bug we're fixing."""
        from ami.jobs.tasks import mark_lost_images_failed

        job, lost_ids = self._make_stuck_job()
        self._mock_consumer_state(
            mock_manager_class, num_pending=0, num_ack_pending=len(lost_ids), num_redelivered=len(lost_ids)
        )

        results = mark_lost_images_failed()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "marked_failed")
        job.refresh_from_db()
        self.assertTrue(job.progress.is_complete())

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_noop_when_job_updated_recently(self, mock_manager_class):
        """Idle-threshold guard: a job that updated_at-bumped within the
        STALLED_JOBS_MAX_MINUTES window is considered in-flight."""
        from ami.jobs.tasks import mark_lost_images_failed

        job, lost_ids = self._make_stuck_job()
        # Reverse the staleness applied by _make_stuck_job.
        Job.objects.filter(pk=job.pk).update(updated_at=datetime.datetime.now())
        self._mock_consumer_state(mock_manager_class, num_pending=0, num_ack_pending=0, num_redelivered=len(lost_ids))

        results = mark_lost_images_failed()

        self.assertEqual(results, [])

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_reconciles_when_num_redelivered_zero_but_redis_has_stuck_ids(self, mock_manager_class):
        """Pre-#1234 Bug A signature: drained consumer, never-redelivered, but
        Redis still has pending ids because an ACK landed before the SREM.
        After dropping the ``num_redelivered > 0`` guard, this case reconciles
        the same way as the ``max_deliver`` exhaustion case — Redis drives the
        outcome, not the consumer's delivery history."""
        from ami.jobs.tasks import mark_lost_images_failed

        job, lost_ids = self._make_stuck_job()
        self._mock_consumer_state(mock_manager_class, num_pending=0, num_ack_pending=0, num_redelivered=0)

        results = mark_lost_images_failed()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "marked_failed")
        job.refresh_from_db()
        self.assertTrue(job.progress.is_complete())

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_mixed_failures_combine_without_double_counting(self, mock_manager_class):
        """Already-SADDed explicit failures stay in ``failed_images`` alongside
        the newly-SADDed lost ids; SADD is idempotent on any accidental overlap.
        Final progress.failed should be explicit + lost, not 2 * overlap."""
        from ami.jobs.tasks import mark_lost_images_failed

        # 20 total, 15 processed, 3 explicit failures, 2 lost → failed_total = 5
        job, lost_ids = self._make_stuck_job(total_images=20, already_processed=15, explicit_failures=3)
        self._mock_consumer_state(mock_manager_class, num_pending=0, num_ack_pending=0, num_redelivered=len(lost_ids))

        results = mark_lost_images_failed()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["lost_count"], len(lost_ids))

        job.refresh_from_db()
        self.assertEqual(job.status, JobState.SUCCESS.value)
        process = job.progress.get_stage("process")
        failed_param = next((p.value for p in process.params if p.key == "failed"), None)
        self.assertEqual(failed_param, 5, f"expected 3 explicit + 2 lost = 5, got {failed_param}")

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_falls_to_failure_when_lost_over_threshold(self, mock_manager_class):
        """FAILURE_THRESHOLD (0.5) preserved: a job that loses >50% of its images
        still lands in FAILURE via the same code path — the helper feeds accurate
        counts, it does not override the completion rules."""
        from ami.jobs.tasks import mark_lost_images_failed

        # 10 total, 3 processed, 0 explicit, 7 lost → 7/10 > 0.5 → FAILURE
        job, lost_ids = self._make_stuck_job(total_images=10, already_processed=3, explicit_failures=0)
        self._mock_consumer_state(mock_manager_class, num_pending=0, num_ack_pending=0, num_redelivered=len(lost_ids))

        results = mark_lost_images_failed()

        self.assertEqual(len(results), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.FAILURE.value, f"expected FAILURE for 7/10 lost; got {job.status}")

    def test_reconcile_skips_when_job_updated_at_bumped_after_candidate_select(self):
        """Race re-validation: between ``mark_lost_images_failed`` reading
        ``candidate_pks`` and ``_reconcile_lost_images`` writing to Redis, a
        late ``process_nats_pipeline_result`` could land and bump ``updated_at``
        past the cutoff. The reconciler must not blindly mark images as failed
        in that window — it would inflate counters (same id processed AND
        failed) and overwrite legitimate progress.

        Verified by calling ``_reconcile_lost_images`` directly with a cutoff
        older than the job's current ``updated_at`` (mimicking the late-result
        bump). Expected: returns ``"raced"``, no progress.errors written, no
        Redis SREM/SADD performed.
        """
        from ami.jobs.tasks import _reconcile_lost_images
        from ami.ml.orchestration.nats_queue import ConsumerState

        job, lost_ids = self._make_stuck_job()
        # Mimic a late result arriving: bump updated_at to "now".
        Job.objects.filter(pk=job.pk).update(updated_at=datetime.datetime.now())

        # Use a cutoff that the live (post-bump) updated_at will fail. Anything
        # in the past works; pick 1 minute ago to be comfortably before "now".
        cutoff = datetime.datetime.now() - datetime.timedelta(minutes=1)
        consumer_state = ConsumerState(num_pending=0, num_ack_pending=0, num_redelivered=len(lost_ids))

        # Snapshot pre-call Redis state so we can assert it was untouched.
        manager = AsyncJobStateManager(job.pk)
        pre_pending = manager.get_pending_image_ids()

        action = _reconcile_lost_images(job.pk, lost_ids, consumer_state, cutoff)

        self.assertEqual(action, "raced")
        job.refresh_from_db()
        # progress.errors untouched: no diagnostic from this run.
        self.assertFalse(
            any("job idle past cutoff" in e for e in job.progress.errors),
            f"raced reconcile must not write progress.errors; got {job.progress.errors}",
        )
        # Redis pending set unchanged: SREM was never issued.
        self.assertEqual(manager.get_pending_image_ids(), pre_pending)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_progress_errors_truncates_long_id_list(self, mock_manager_class):
        """JSONB cap: ``progress.errors`` is rendered in the UI and shipped
        in the job detail payload. A 200-image job's full sorted id list
        would be multi-KB per error entry. The diagnostic written to
        ``progress.errors`` previews the first
        ``_PROGRESS_ERROR_ID_PREVIEW_LIMIT`` ids and notes "and N more"; the
        full list is logged separately to the per-job logger.
        """
        from ami.jobs.tasks import _PROGRESS_ERROR_ID_PREVIEW_LIMIT, mark_lost_images_failed

        # 25 lost > limit (10) → "and 15 more"
        job, lost_ids = self._make_stuck_job(total_images=30, already_processed=4, explicit_failures=1)
        self.assertGreater(len(lost_ids), _PROGRESS_ERROR_ID_PREVIEW_LIMIT)
        self._mock_consumer_state(mock_manager_class, num_pending=0, num_ack_pending=0, num_redelivered=len(lost_ids))

        results = mark_lost_images_failed()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "marked_failed")

        job.refresh_from_db()
        diagnostic_entry = next((e for e in job.progress.errors if "job idle past cutoff" in e), None)
        self.assertIsNotNone(diagnostic_entry, f"diagnostic missing; got errors={job.progress.errors}")
        extra = len(lost_ids) - _PROGRESS_ERROR_ID_PREVIEW_LIMIT
        self.assertIn(f"and {extra} more", diagnostic_entry)

        # The id list in progress.errors must include the first preview ids
        # but not the trailing ones. Pick any id beyond the preview window
        # and assert it's absent.
        sorted_ids = sorted(lost_ids)
        self.assertIn(sorted_ids[0], diagnostic_entry)
        self.assertNotIn(sorted_ids[-1], diagnostic_entry)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_jobs_health_check_runs_lost_images_before_stale_jobs(self, mock_manager_class):
        """Integration: jobs_health_check should unstick lost-images jobs before
        check_stale_jobs gets a chance to REVOKE them. A job that would otherwise
        be revoked (status running + updated_at past cutoff) lands in SUCCESS via
        the lost-images path."""
        from ami.jobs.tasks import jobs_health_check

        job, lost_ids = self._make_stuck_job()
        self._mock_consumer_state(mock_manager_class, num_pending=0, num_ack_pending=0, num_redelivered=len(lost_ids))

        result = jobs_health_check()

        self.assertEqual(result["lost_images"]["fixed"], 1, f"result={result}")
        # stale_jobs sub-check must not have revoked anything — the job already
        # terminated in SUCCESS in the earlier step, so it is no longer
        # running_state by the time check_stale_jobs runs.
        self.assertEqual(result["stale_jobs"]["fixed"], 0, f"result={result}")

        job.refresh_from_db()
        self.assertEqual(job.status, JobState.SUCCESS.value)
