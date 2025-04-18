# from rich import print
import logging
import threading

from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.test import APIRequestFactory, APITestCase

from ami.base.serializers import reverse_with_params
from ami.jobs.models import (
    BatchedJobLogHandler,
    Job,
    JobLogHandler,
    JobProgress,
    JobState,
    MLJob,
    SourceImageCollectionPopulateJob,
)
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

        assign_perm(Project.Permissions.RUN_JOB, self.user, self.project)

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

    def test_job_logs_api(self):
        """Test the storage and retrieval of job logs using the standard JobLogHandler."""
        job_name = "Test job for logs"

        # Create a job
        job_data = self._create_job(job_name, start_now=False)
        job_id = job_data["id"]
        job = Job.objects.get(pk=job_id)

        # Check that Job.logger has propagate=False (as it should)
        job_logger = job.logger
        self.assertFalse(job_logger.propagate, "Job logger should have propagate=False")

        # Check that it uses JobLogHandler
        self.assertEqual(len(job_logger.handlers), 1, "Job logger should have exactly one handler")
        self.assertIsInstance(job_logger.handlers[0], JobLogHandler, "Job logger should use JobLogHandler")

        # Use the Job.logger property directly to add logs
        job_logger.setLevel(logging.DEBUG)

        # Add various log messages using the job logger
        job_logger.debug("Debug message")
        job_logger.info("Info message")
        job_logger.warning("Warning message")
        job_logger.error("Error message 1")
        job_logger.error("Error message 2")
        job_logger.critical("Critical message")

        # Create a second logger instance to simulate concurrent logging
        # This would normally cause issues with the old array-based method
        concurrent_logger = logging.getLogger(f"test.jobs.concurrent.{job.pk}")
        concurrent_logger.addHandler(job_logger.handlers[0])  # Add the JobLogHandler
        concurrent_logger.setLevel(logging.DEBUG)
        concurrent_logger.propagate = False  # Match job logger configuration

        # Simulate concurrent logging from different sources
        for i in range(5):
            concurrent_logger.info(f"Concurrent message {i}")

        # Retrieve the job via API
        self.client.force_authenticate(user=self.user)
        job_detail_url = reverse_with_params("api:job-detail", args=[job_id], params={"project_id": self.project.pk})
        resp = self.client.get(job_detail_url)
        self.assertEqual(resp.status_code, 200)

        # Check if logs are present in the response
        data = resp.json()
        self.assertIn("log_entries", data)
        self.assertIn("errors", data)

        # Verify log entries are returned in the expected format
        log_entries = data["log_entries"]
        self.assertGreaterEqual(len(log_entries), 9)  # 9 log messages total

        # Check that error logs are correctly identified
        errors = data["errors"]
        self.assertEqual(len(errors), 3)  # 3 error/critical messages

        # Verify the error messages
        error_messages = [error["message"] for error in errors]
        self.assertIn("Error message 1", error_messages)
        self.assertIn("Error message 2", error_messages)
        self.assertIn("Critical message", error_messages)

        # Verify DB entries match what's in the API response
        from ami.jobs.models import JobLog

        db_logs = JobLog.objects.filter(job_id=job_id).order_by("-timestamp")
        self.assertEqual(db_logs.count(), len(log_entries))

        # Check that the DB entries for error logs match
        db_errors = JobLog.objects.filter(job_id=job_id, is_error=True).order_by("-timestamp")
        self.assertEqual(db_errors.count(), len(errors))

    def test_batched_job_log_handler(self):
        """Test the batched log handler with no timer and only manual flushing."""
        job_name = "Test job for batched logs"

        # Create a job
        job_data = self._create_job(job_name, start_now=False)
        job_id = job_data["id"]
        job = Job.objects.get(pk=job_id)

        # Create a simplified version of batched handler with no timer
        class SimplifiedBatchedHandler(BatchedJobLogHandler):
            def __init__(self, job, batch_size=None):
                # Skip the parent init which sets up the timer
                logging.Handler.__init__(self)
                self.job = job
                self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE
                self.queue = []
                self._lock = threading.Lock()
                # Add this attribute to avoid AttributeError in parent close() method
                self._timer = None
                self.batch_age_seconds = 5  # Add this to avoid AttributeError

        # Create logger and add the simplified handler
        batched_logger = logging.getLogger(f"ami.jobs.batched.{job.pk}")
        batched_handler = SimplifiedBatchedHandler(job, batch_size=5)
        batched_logger.addHandler(batched_handler)
        batched_logger.setLevel(logging.DEBUG)
        batched_logger.propagate = False

        # Add logs below batch size
        for i in range(3):
            batched_logger.info(f"Below batch size message {i}")

        # Manually verify no auto-flush yet
        from ami.jobs.models import JobLog

        db_logs = JobLog.objects.filter(job_id=job_id).order_by("-timestamp")
        self.assertEqual(db_logs.count(), 0)

        # Manually flush
        batched_handler.flush()

        # Verify logs were written
        db_logs = JobLog.objects.filter(job_id=job_id).order_by("-timestamp")
        self.assertEqual(db_logs.count(), 3)

        # Add some errors and manually flush
        batched_logger.error("Batched error 1")
        batched_logger.error("Batched error 2")
        batched_handler.flush()

        # Verify error logs
        db_logs = JobLog.objects.filter(job_id=job_id).order_by("-timestamp")
        self.assertEqual(db_logs.count(), 5)  # 3 previous + 2 new logs

        # Check errors are properly flagged
        db_errors = JobLog.objects.filter(job_id=job_id, is_error=True).order_by("-timestamp")
        self.assertEqual(db_errors.count(), 2)
