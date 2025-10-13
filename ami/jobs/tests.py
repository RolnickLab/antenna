# from rich import print
import datetime
import logging
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone
from guardian.shortcuts import assign_perm
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import Job, JobProgress, JobState, MLJob, SourceImageCollectionPopulateJob
from ami.main.models import Project, SourceImage, SourceImageCollection
from ami.ml.models import Pipeline
from ami.users.models import User

logger = logging.getLogger(__name__)


class TestJobProgress(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Test project")
        self.source_image_collection = SourceImageCollection.objects.create(
            name="Test collection",
            project=self.project,
        )
        self.pipeline = Pipeline.objects.create(
            name="Test ML pipeline",
            description="Test ML pipeline",
        )
        self.pipeline.projects.add(self.project)

    def test_create_job(self):
        job = Job.objects.create(project=self.project, name="Test job - create only")
        self.assertIsInstance(job.progress, JobProgress)
        self.assertEqual(job.progress.summary.progress, 0)
        self.assertEqual(job.progress.stages, [])

    def test_create_job_with_delay(self):
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job",
            delay=1,
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )
        self.assertEqual(job.progress.stages[0].key, "delay")
        self.assertEqual(job.progress.stages[0].progress, 0)
        self.assertEqual(job.progress.stages[0].status, JobState.CREATED)

        self.assertEqual(job.status, JobState.CREATED.value)
        self.assertEqual(job.progress.summary.progress, 0)
        self.assertEqual(job.progress.summary.status, JobState.CREATED)

        job.run()

        self.assertEqual(job.status, JobState.SUCCESS.value)
        self.assertEqual(job.progress.summary.progress, 1)
        self.assertEqual(job.progress.summary.status, JobState.SUCCESS)
        self.assertEqual(job.progress.stages[0].progress, 1)
        self.assertEqual(job.progress.stages[0].status, JobState.SUCCESS)


class TestJobView(APITestCase):
    """
    Test the jobs API endpoints.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Jobs Test Project")
        self.test_image = SourceImage.objects.create(path="test.jpg", project=self.project)
        self.source_image_collection = SourceImageCollection.objects.create(
            name="Test collection",
            project=self.project,
        )
        self.source_image_collection.images.add(self.test_image)
        self.job = Job.objects.create(
            job_type_key=SourceImageCollectionPopulateJob.key,
            project=self.project,
            name="Test populate job",
            delay=0,
            source_image_collection=self.source_image_collection,
        )

        self.user = User.objects.create_user(  # type: ignore
            email="testuser@insectai.org",
            is_staff=True,
            is_active=True,
            is_superuser=True,
        )
        self.factory = APIRequestFactory()

    def test_get_job(self):
        self.client.force_authenticate(user=self.user)
        jobs_retrieve_url = reverse_with_params("api:job-detail", args=[self.job.pk])
        resp = self.client.get(jobs_retrieve_url + f"?project_id={self.project.pk}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], self.job.pk)

    def test_get_job_list(self):
        # resp = self.client.get("/api/jobs/")
        jobs_list_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})
        resp = self.client.get(jobs_list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_create_job_unauthenticated(self):
        jobs_create_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})
        job_data = {
            "project_id": self.project.pk,
            "source_image_collection_id": self.source_image_collection.pk,
            "name": "Test job unauthenticated",
            "delay": 0,
            "job_type_key": SourceImageCollectionPopulateJob.key,
        }
        self.client.force_authenticate(user=None)
        resp = self.client.post(jobs_create_url, job_data)
        self.assertEqual(resp.status_code, 401)

    def _create_job(self, name: str, start_now: bool = True):
        jobs_create_url = reverse_with_params("api:job-list", params={"project_id": self.project.pk})

        self.client.force_authenticate(user=self.user)
        job_data = {
            "project_id": self.job.project.pk,
            "name": name,
            "source_image_collection_id": self.source_image_collection.pk,
            "delay": 0,
            "start_now": start_now,
            "job_type_key": SourceImageCollectionPopulateJob.key,
        }
        resp = self.client.post(jobs_create_url, job_data)
        self.client.force_authenticate(user=None)
        self.assertEqual(resp.status_code, 201)
        return resp.json()

    def test_create_job(self):
        job_name = "Test job - Start but don't run"
        data = self._create_job(job_name, start_now=False)
        self.assertEqual(data["project"]["id"], self.project.pk)
        self.assertEqual(data["name"], job_name)

        job = Job.objects.get(pk=data["id"])
        self.assertEqual(job.status, JobState.CREATED.value)

        # @TODO This should be CREATED as well, but it is SUCCESS!
        # progress = JobProgress(**data["progress"])
        # self.assertEqual(progress.summary.status, JobState.CREATED)

    def test_run_job(self):
        data = self._create_job("Test run job", start_now=False)

        job_id = data["id"]
        jobs_run_url = reverse_with_params(
            "api:job-run", args=[job_id], params={"no_async": True, "project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        # give user run permission

        assign_perm(Project.Permissions.RUN_POPULATE_CAPTURES_COLLECTION_JOB, self.user, self.project)

        resp = self.client.post(jobs_run_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], job_id)
        self.assertEqual(data["status"], JobState.SUCCESS.value)
        progress = JobProgress(**data["progress"])
        self.assertEqual(progress.summary.status, JobState.SUCCESS)
        self.assertEqual(progress.summary.progress, 1.0)

        # @TODO test async job
        # self.job.refresh_from_db()
        # self.assertIsNotNone(self.job.task_id)

    def test_retry_job(self):
        data = self._create_job("Test retry job", start_now=False)
        job_id = data["id"]
        jobs_retry_url = reverse_with_params(
            "api:job-retry", args=[job_id], params={"no_async": True, "project_id": self.project.pk}
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(jobs_retry_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], job_id)
        self.assertEqual(data["status"], JobState.SUCCESS.value)
        progress = JobProgress(**data["progress"])
        self.assertEqual(progress.summary.status, JobState.SUCCESS)

        # @TODO this should be 1.0, why is the progress object not being properly updated?
        # self.assertEqual(progress.summary.progress, 1.0)

    def test_run_job_unauthenticated(self):
        jobs_run_url = reverse_with_params("api:job-run", args=[self.job.pk], params={"project_id": self.project.pk})
        self.client.force_authenticate(user=None)
        resp = self.client.post(jobs_run_url)
        self.assertEqual(resp.status_code, 401)

    def test_cancel_job(self):
        # This cannot be tested until we have a way to cancel jobs
        # and a way to run async tasks in tests.
        pass


class TestJobStatusChecking(TestCase):
    """
    Test the job status checking functionality.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Status Check Test Project")
        self.pipeline = Pipeline.objects.create(
            name="Test ML pipeline",
            description="Test ML pipeline",
        )
        self.pipeline.projects.add(self.project)
        self.source_image_collection = SourceImageCollection.objects.create(
            name="Test collection",
            project=self.project,
        )

    def test_check_status_no_task_id_recently_scheduled(self):
        """Test that recently scheduled jobs without task_id are not marked as failed."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - no task_id",
            scheduled_at=timezone.now(),
        )

        status_changed = job.check_status()

        self.assertFalse(status_changed)
        self.assertEqual(job.status, JobState.CREATED.value)
        self.assertIsNotNone(job.last_checked_at)

    def test_check_status_no_task_id_old_scheduled(self):
        """Test that old scheduled jobs without task_id are marked as failed."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - stale no task_id",
            scheduled_at=timezone.now() - datetime.timedelta(minutes=10),
        )

        status_changed = job.check_status()

        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE.value)
        self.assertIsNotNone(job.finished_at)
        self.assertIsNotNone(job.last_checked_at)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_with_matching_status(self, mock_async_result):
        """Test that jobs with matching Celery status are not changed."""
        mock_task = MagicMock()
        mock_task.status = JobState.STARTED.value
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - matching status",
            task_id="test-task-id-123",
            status=JobState.STARTED.value,
            started_at=timezone.now(),
        )

        status_changed = job.check_status()

        self.assertFalse(status_changed)
        self.assertEqual(job.status, JobState.STARTED.value)
        self.assertIsNotNone(job.last_checked_at)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_with_mismatched_status(self, mock_async_result):
        """Test that jobs with mismatched Celery status are updated."""
        mock_task = MagicMock()
        mock_task.status = JobState.FAILURE.value
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - mismatched status",
            task_id="test-task-id-456",
            status=JobState.STARTED.value,
            started_at=timezone.now(),
        )

        status_changed = job.check_status()

        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE.value)
        self.assertIsNotNone(job.finished_at)
        self.assertIsNotNone(job.last_checked_at)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_stale_running_job(self, mock_async_result):
        """Test that jobs running for too long are marked as failed."""
        mock_task = MagicMock()
        mock_task.status = JobState.STARTED.value
        mock_async_result.return_value = mock_task

        # Create job that started longer than MAX_JOB_RUNTIME_SECONDS ago
        stale_time = datetime.timedelta(seconds=Job.MAX_JOB_RUNTIME_SECONDS + 3600)  # 1 hour past limit
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - stale running",
            task_id="test-task-id-789",
            status=JobState.STARTED.value,
            started_at=timezone.now() - stale_time,
        )

        status_changed = job.check_status()

        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE.value)
        self.assertIsNotNone(job.finished_at)
        # Verify task was attempted to be revoked
        mock_task.revoke.assert_called_once_with(terminate=True)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_stuck_pending(self, mock_async_result):
        """Test that jobs stuck in PENDING for too long are marked as failed."""
        mock_task = MagicMock()
        mock_task.status = JobState.PENDING.value
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - stuck pending",
            task_id="test-task-id-pending",
            status=JobState.PENDING.value,
            scheduled_at=timezone.now() - datetime.timedelta(minutes=15),
        )

        status_changed = job.check_status()

        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE.value)
        self.assertIsNotNone(job.finished_at)

    def test_check_status_does_not_check_completed_jobs(self):
        """Test that completed jobs are not checked unless forced."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - completed",
            task_id="test-task-id-completed",
            status=JobState.SUCCESS.value,
            finished_at=timezone.now(),
        )

        status_changed = job.check_status(force=False)

        self.assertFalse(status_changed)
        self.assertEqual(job.status, JobState.SUCCESS.value)
        self.assertIsNotNone(job.last_checked_at)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_forces_check_on_completed_jobs(self, mock_async_result):
        """Test that force=True checks even completed jobs."""
        mock_task = MagicMock()
        mock_task.status = JobState.SUCCESS.value
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - force check",
            task_id="test-task-id-force",
            status=JobState.SUCCESS.value,
            finished_at=timezone.now(),
        )

        status_changed = job.check_status(force=True)

        # Status shouldn't change since Celery status matches
        self.assertFalse(status_changed)
        self.assertIsNotNone(job.last_checked_at)

    @patch("ami.jobs.tasks.cache")
    @patch("ami.jobs.models.Job.objects")
    def test_check_unfinished_jobs_with_lock(self, mock_job_objects, mock_cache):
        """Test that check_unfinished_jobs uses locking to prevent duplicates."""
        from ami.jobs.tasks import check_unfinished_jobs

        # Simulate lock already acquired
        mock_cache.add.return_value = False

        result = check_unfinished_jobs()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "already_running")
        mock_cache.add.assert_called_once()
        mock_cache.delete.assert_not_called()

    @patch("ami.jobs.tasks.cache")
    def test_check_unfinished_jobs_processes_jobs(self, mock_cache):
        """Test that check_unfinished_jobs processes unfinished jobs."""
        from ami.jobs.tasks import check_unfinished_jobs

        # Allow lock to be acquired
        mock_cache.add.return_value = True

        # Create some unfinished jobs
        job1 = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Unfinished job 1",
            status=JobState.STARTED.value,
            task_id="test-task-1",
            started_at=timezone.now(),
            last_checked_at=timezone.now() - datetime.timedelta(minutes=5),
        )

        job2 = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Unfinished job 2",
            status=JobState.PENDING.value,
            task_id="test-task-2",
            scheduled_at=timezone.now() - datetime.timedelta(minutes=3),
        )

        # Create a completed job (should not be checked)
        Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Completed job",
            status=JobState.SUCCESS.value,
            finished_at=timezone.now(),
        )

        with patch("ami.jobs.models.AsyncResult") as mock_async_result:
            mock_task = MagicMock()
            mock_task.status = JobState.STARTED.value
            mock_async_result.return_value = mock_task

            result = check_unfinished_jobs()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_unfinished"], 2)
        self.assertGreaterEqual(result["checked"], 1)

        # Verify lock was released
        mock_cache.delete.assert_called_once()

        # Verify jobs were checked
        job1.refresh_from_db()
        job2.refresh_from_db()
        self.assertIsNotNone(job1.last_checked_at)
        self.assertIsNotNone(job2.last_checked_at)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_task_disappeared_with_retry(self, mock_async_result):
        """Test that jobs with disappeared tasks are retried if they just started."""
        mock_task = MagicMock()
        mock_task.status = None  # Task not found
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - task disappeared",
            task_id="test-task-disappeared",
            status=JobState.STARTED.value,
            started_at=timezone.now() - datetime.timedelta(minutes=2),  # Started 2 mins ago
            pipeline=self.pipeline,
            source_image_collection=self.source_image_collection,
        )

        # Mock the retry method
        with patch.object(job, "retry") as mock_retry:
            status_changed = job.check_status(auto_retry=True)

            # Should attempt retry
            mock_retry.assert_called_once_with(async_task=True)
            self.assertTrue(status_changed)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_task_disappeared_no_retry_old_job(self, mock_async_result):
        """Test that old jobs with disappeared tasks are marked failed, not retried."""
        mock_task = MagicMock()
        mock_task.status = None  # Task not found
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - old disappeared task",
            task_id="test-task-old-disappeared",
            status=JobState.STARTED.value,
            started_at=timezone.now() - datetime.timedelta(minutes=10),  # Started 10 mins ago
        )

        status_changed = job.check_status(auto_retry=True)

        # Should not retry, just mark as failed
        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE.value)
        self.assertIsNotNone(job.finished_at)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_task_disappeared_auto_retry_disabled(self, mock_async_result):
        """Test that auto_retry=False prevents automatic retry."""
        mock_task = MagicMock()
        mock_task.status = None  # Task not found
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - no auto retry",
            task_id="test-task-no-retry",
            status=JobState.STARTED.value,
            started_at=timezone.now() - datetime.timedelta(minutes=2),
        )

        status_changed = job.check_status(auto_retry=False)

        # Should not retry, just mark as failed
        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE.value)
        self.assertIsNotNone(job.finished_at)

    @patch("ami.jobs.models.AsyncResult")
    def test_check_status_task_pending_but_job_running(self, mock_async_result):
        """Test that PENDING status from Celery when job thinks it's running indicates disappeared task."""
        mock_task = MagicMock()
        mock_task.status = "PENDING"  # Celery returns PENDING for unknown tasks
        mock_async_result.return_value = mock_task

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - pending but should be running",
            task_id="test-task-fake-pending",
            status=JobState.STARTED.value,
            started_at=timezone.now() - datetime.timedelta(minutes=2),
        )

        status_changed = job.check_status(auto_retry=False)

        # Should detect this as a disappeared task
        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE.value)


class TestJobConcurrency(TestCase):
    """Test concurrent updates to jobs from multiple workers."""

    def setUp(self):
        self.project = Project.objects.create(name="Test project")
        self.pipeline = Pipeline.objects.create(
            name="Test ML pipeline",
            description="Test ML pipeline",
        )
        self.pipeline.projects.add(self.project)

    def test_atomic_job_update_context_manager(self):
        """Test that atomic_job_update locks and updates the job."""
        from ami.jobs.models import atomic_job_update

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - atomic update",
            pipeline=self.pipeline,
        )

        # Use the context manager to update the job
        with atomic_job_update(job.pk) as locked_job:
            locked_job.logs.stdout.insert(0, "Test log message")
            locked_job.save(update_fields=["logs"], update_progress=False)

        # Refresh from DB and verify the update persisted
        job.refresh_from_db()
        self.assertIn("Test log message", job.logs.stdout)

    def test_concurrent_log_writes(self):
        """Test that concurrent log writes don't overwrite each other."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - concurrent logs",
            pipeline=self.pipeline,
        )

        # Simulate multiple workers adding logs
        messages = [f"Log message {i}" for i in range(5)]

        for msg in messages:
            # Use the logger which uses JobLogHandler with atomic updates
            job.logger.info(msg)

        # Refresh from DB
        job.refresh_from_db()

        # All messages should be present (no overwrites)
        for msg in messages:
            # Messages are formatted with timestamps and log levels
            self.assertTrue(any(msg in log for log in job.logs.stdout), f"Message '{msg}' not found in logs")

    def test_log_handler_with_atomic_update(self):
        """Test that JobLogHandler properly uses atomic updates."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - log handler",
            pipeline=self.pipeline,
        )

        # Get the logger (which adds JobLogHandler)
        job_logger = job.logger

        # Add multiple log messages
        job_logger.info("Info message")
        job_logger.warning("Warning message")
        job_logger.error("Error message")

        # Refresh from DB
        job.refresh_from_db()

        # Verify all logs are present
        self.assertTrue(any("Info message" in log for log in job.logs.stdout))
        self.assertTrue(any("Warning message" in log for log in job.logs.stdout))
        self.assertTrue(any("Error message" in log for log in job.logs.stdout))

        # Verify error also appears in stderr
        self.assertTrue(any("Error message" in err for err in job.logs.stderr))

    def test_max_log_length_enforcement(self):
        """Test that log length limits are enforced with atomic updates."""
        import logging

        from ami.jobs.models import JobLogHandler

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - max logs",
            pipeline=self.pipeline,
        )

        # Temporarily suppress log output to avoid spamming test results
        job_logger = job.logger
        original_level = job_logger.level
        job_logger.setLevel(logging.CRITICAL)

        try:
            # Add more logs than the max
            max_logs = JobLogHandler.max_log_length
            for i in range(max_logs + 10):
                job.logger.info(f"Message {i}")

            # Refresh from DB
            job.refresh_from_db()

            # Should not exceed max length
            self.assertLessEqual(len(job.logs.stdout), max_logs)
            self.assertLessEqual(len(job.logs.stderr), max_logs)
        finally:
            # Restore original log level
            job_logger.setLevel(original_level)

    def test_log_length_never_decreases(self):
        """Test that the save method prevents logs from getting shorter."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - log safety",
            pipeline=self.pipeline,
        )

        # Add some logs
        job.logger.info("Log message 1")
        job.logger.info("Log message 2")
        job.logger.info("Log message 3")

        job.refresh_from_db()
        initial_log_count = len(job.logs.stdout)
        self.assertGreaterEqual(initial_log_count, 3)

        # Simulate stale in-memory job with fewer logs (like what happens with concurrent workers)
        stale_job = Job.objects.get(pk=job.pk)
        stale_job.logs.stdout = stale_job.logs.stdout[:1]  # Artificially reduce logs to just 1

        # Try to save with update_fields that doesn't include logs
        # The safety check should prevent logs from being overwritten
        stale_job.status = JobState.STARTED
        stale_job.save(update_fields=["status", "progress"])

        # Verify logs weren't reduced
        stale_job.refresh_from_db()
        final_log_count = len(stale_job.logs.stdout)
        self.assertEqual(
            final_log_count,
            initial_log_count,
            "Logs should never decrease in length when not explicitly updating logs",
        )

    def test_log_can_be_explicitly_updated(self):
        """Test that logs CAN be updated when explicitly included in update_fields."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test job - explicit log update",
            pipeline=self.pipeline,
        )

        # Add initial logs
        job.logger.info("Log message 1")
        job.logger.info("Log message 2")

        job.refresh_from_db()

        # Explicitly update logs (like JobLogHandler does)
        job.logs.stdout = ["New log only"]
        job.save(update_fields=["logs"])

        # Verify logs were updated as requested
        job.refresh_from_db()
        self.assertEqual(len(job.logs.stdout), 1)
        self.assertEqual(job.logs.stdout[0], "New log only")
