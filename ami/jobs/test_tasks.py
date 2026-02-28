"""
E2E tests for ami.jobs.tasks, focusing on error handling in process_nats_pipeline_result.

This test suite verifies the critical error handling path when PipelineResultsError
is received instead of successful pipeline results.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import Job, JobDispatchMode, JobState, MLJob
from ami.jobs.tasks import process_nats_pipeline_result
from ami.main.models import Detection, Project, SourceImage, SourceImageCollection
from ami.ml.models import Algorithm, Pipeline
from ami.ml.models.algorithm import AlgorithmTaskType
from ami.ml.orchestration.async_job_state import AsyncJobStateManager, _lock_key
from ami.ml.schemas import PipelineResultsError, PipelineResultsResponse, SourceImageResponse
from ami.users.models import User

logger = logging.getLogger(__name__)


class TestProcessNatsPipelineResultError(TestCase):
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
    def test_process_nats_pipeline_result_error_concurrent_locking(self, mock_manager_class):
        """
        Test that error results respect locking mechanism.

        Verifies race condition handling when multiple workers
        process error results simultaneously.
        """
        # Simulate lock held by another task
        lock_key = _lock_key(self.job.pk)
        cache.set(lock_key, "other-task-id", timeout=60)

        # Create error result
        error_data = self._create_error_result(image_id=str(self.images[0].pk))
        reply_subject = "tasks.reply.test789"

        # Task should raise retry exception when lock not acquired
        # The task internally calls self.retry() which raises a Retry exception
        from celery.exceptions import Retry

        with self.assertRaises(Retry):
            process_nats_pipeline_result.apply(
                kwargs={
                    "job_id": self.job.pk,
                    "result_data": error_data,
                    "reply_subject": reply_subject,
                }
            )

        # Assert: Progress was NOT updated (lock not acquired)
        manager = AsyncJobStateManager(self.job.pk)
        progress = manager.get_progress("process")
        self.assertEqual(progress.processed, 0)

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

        # Create error result data
        result_data = [
            {
                "reply_subject": "test.reply.error.1",
                "result": {
                    "error": "Image processing timeout",
                    "image_id": str(self.image.pk),
                },
            }
        ]

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
