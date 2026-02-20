"""Integration tests for async job resource cleanup (NATS and Redis)."""

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.test import TestCase
from nats.js.errors import NotFoundError

from ami.jobs.models import Job, JobDispatchMode, JobState, MLJob
from ami.jobs.tasks import _update_job_progress, update_job_failure, update_job_status
from ami.main.models import Project, ProjectFeatureFlags, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.ml.orchestration.async_job_state import AsyncJobStateManager
from ami.ml.orchestration.jobs import queue_images_to_nats
from ami.ml.orchestration.nats_queue import TaskQueueManager


class TestCleanupAsyncJobResources(TestCase):
    """Test cleanup of NATS and Redis resources for async ML jobs."""

    def setUp(self):
        """Set up test fixtures with async_pipeline_workers enabled."""
        # Create project with async_pipeline_workers feature flag enabled
        self.project = Project.objects.create(
            name="Test Cleanup Project",
            feature_flags=ProjectFeatureFlags(async_pipeline_workers=True),
        )

        # Create pipeline
        self.pipeline = Pipeline.objects.create(
            name="Test Cleanup Pipeline",
            slug="test-cleanup-pipeline",
            description="Pipeline for cleanup tests",
        )
        self.pipeline.projects.add(self.project)

        # Create source image collection with images
        self.collection = SourceImageCollection.objects.create(
            name="Test Cleanup Collection",
            project=self.project,
        )

        # Create test images
        self.images = [
            SourceImage.objects.create(
                path=f"test_image_{i}.jpg",
                public_base_url="https://example.com",
                project=self.project,
            )
            for i in range(3)
        ]
        for image in self.images:
            self.collection.images.add(image)

    def _verify_resources_created(self, job_id: int):
        """
        Verify that both Redis and NATS resources were created.

        Args:
            job_id: The job ID to check
        """
        # Verify Redis keys exist
        state_manager = AsyncJobStateManager(job_id)
        for stage in state_manager.STAGES:
            pending_key = state_manager._get_pending_key(stage)
            self.assertIsNotNone(cache.get(pending_key), f"Redis key {pending_key} should exist")
        total_key = state_manager._total_key
        self.assertIsNotNone(cache.get(total_key), f"Redis key {total_key} should exist")

        # Verify NATS stream and consumer exist
        async def check_nats_resources():
            manager = TaskQueueManager()
            stream_name = manager._get_stream_name(job_id)
            consumer_name = manager._get_consumer_name(job_id)

            # Get JetStream context
            _, js = await manager._get_connection()

            # Try to get stream info - should succeed if created
            stream_exists = True
            try:
                await js.stream_info(stream_name)
            except NotFoundError:
                stream_exists = False

            # Try to get consumer info - should succeed if created
            consumer_exists = True
            try:
                await js.consumer_info(stream_name, consumer_name)
            except NotFoundError:
                consumer_exists = False

            return stream_exists, consumer_exists

        stream_exists, consumer_exists = async_to_sync(check_nats_resources)()

        self.assertTrue(stream_exists, f"NATS stream for job {job_id} should exist")
        self.assertTrue(consumer_exists, f"NATS consumer for job {job_id} should exist")

    def _create_job_with_queued_images(self) -> Job:
        """
        Helper to create an ML job and queue images to NATS/Redis.

        Returns:
            Job instance with images queued to NATS and state initialized in Redis
        """
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Cleanup Job",
            pipeline=self.pipeline,
            source_image_collection=self.collection,
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )

        # Queue images to NATS (also initializes Redis state)
        queue_images_to_nats(job, self.images)

        # Verify resources were actually created
        self._verify_resources_created(job.pk)

        return job

    def _verify_resources_cleaned(self, job_id: int):
        """
        Verify that both Redis and NATS resources are cleaned up.

        Args:
            job_id: The job ID to check
        """
        # Verify Redis keys are deleted
        state_manager = AsyncJobStateManager(job_id)
        for stage in state_manager.STAGES:
            pending_key = state_manager._get_pending_key(stage)
            self.assertIsNone(cache.get(pending_key), f"Redis key {pending_key} should be deleted")
        total_key = state_manager._total_key
        self.assertIsNone(cache.get(total_key), f"Redis key {total_key} should be deleted")

        # Verify NATS stream and consumer are deleted
        async def check_nats_resources():
            manager = TaskQueueManager()
            stream_name = manager._get_stream_name(job_id)
            consumer_name = manager._get_consumer_name(job_id)

            # Get JetStream context
            _, js = await manager._get_connection()

            # Try to get stream info - should fail if deleted
            stream_exists = True
            try:
                await js.stream_info(stream_name)
            except NotFoundError:
                stream_exists = False

            # Try to get consumer info - should fail if deleted
            consumer_exists = True
            try:
                await js.consumer_info(stream_name, consumer_name)
            except NotFoundError:
                consumer_exists = False

            return stream_exists, consumer_exists

        stream_exists, consumer_exists = async_to_sync(check_nats_resources)()

        self.assertFalse(stream_exists, f"NATS stream for job {job_id} should be deleted")
        self.assertFalse(consumer_exists, f"NATS consumer for job {job_id} should be deleted")

    def test_cleanup_on_job_completion(self):
        """Test that resources are cleaned up when job completes successfully."""
        job = self._create_job_with_queued_images()

        # Simulate job completion: complete all stages (collect, process, then results)
        _update_job_progress(job.pk, stage="collect", progress_percentage=1.0, complete_state=JobState.SUCCESS)
        _update_job_progress(job.pk, stage="process", progress_percentage=1.0, complete_state=JobState.SUCCESS)
        _update_job_progress(job.pk, stage="results", progress_percentage=1.0, complete_state=JobState.SUCCESS)

        # Verify cleanup happened
        self._verify_resources_cleaned(job.pk)

    def test_cleanup_on_job_failure(self):
        """Test that resources are cleaned up when job fails."""
        job = self._create_job_with_queued_images()

        # Set task_id so the failure handler can find the job
        job.task_id = "test-task-failure-123"
        job.save()

        # Simulate job failure by calling the failure signal handler
        update_job_failure(
            sender=None,
            task_id=job.task_id,
            exception=Exception("Test failure"),
        )

        # Verify cleanup happened
        self._verify_resources_cleaned(job.pk)

    def test_cleanup_on_job_revoked(self):
        """Test that resources are cleaned up when job is revoked/cancelled."""
        job = self._create_job_with_queued_images()

        # Create a mock task request object for the signal handler
        class MockRequest:
            def __init__(self):
                self.kwargs = {"job_id": job.pk}

        class MockTask:
            def __init__(self, job_id):
                self.request = MockRequest()
                self.request.kwargs["job_id"] = job_id

        # Simulate job revocation by calling the postrun signal handler with REVOKED state
        update_job_status(
            sender=None,
            task_id="test-task-revoked-456",
            task=MockTask(job.pk),
            state=JobState.REVOKED,
        )

        # Verify cleanup happened
        self._verify_resources_cleaned(job.pk)
