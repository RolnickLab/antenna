# from rich import print
import logging

from django.test import TestCase
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

    def test_check_status_missing_task_id(self):
        """Test that jobs scheduled but never assigned a task_id are marked failed."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - No Task ID",
            status=JobState.PENDING,
            scheduled_at=timezone.now() - timedelta(minutes=10),
            task_id=None,
        )

        status_changed = job.check_status(force=True, save=True)

        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE)
        self.assertIsNotNone(job.last_checked_at)
        # Check that error was logged
        self.assertTrue(any("never got a task_id" in msg for msg in job.logs.stderr))

    def test_check_status_not_missing_task_id_when_recent(self):
        """Test that jobs without task_id but scheduled recently are not marked failed."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Recent No Task ID",
            status=JobState.PENDING,
            scheduled_at=timezone.now() - timedelta(minutes=1),  # Only 1 minute old
            task_id=None,
        )

        status_changed = job.check_status(force=True, save=True)

        self.assertFalse(status_changed)
        self.assertEqual(job.status, JobState.PENDING)

    def test_check_status_disappeared_task(self):
        """Test that started jobs with disappeared tasks are marked failed."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Disappeared Task",
            status=JobState.STARTED,
            started_at=timezone.now() - timedelta(minutes=10),
            task_id="nonexistent-task-id-12345",
        )

        status_changed = job.check_status(force=True, save=True)

        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE)
        # Check that error was logged
        self.assertTrue(any("disappeared from Celery" in msg for msg in job.logs.stderr))

    def test_check_status_max_runtime_exceeded(self):
        """Test that jobs running too long are marked failed."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Max Runtime",
            status=JobState.STARTED,
            started_at=timezone.now() - timedelta(days=8),  # 8 days (max is 7)
            task_id="some-task-id",
        )

        status_changed = job.check_status(force=True, save=True)

        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE)
        # Refresh from DB to get the latest logs
        job.refresh_from_db()
        # Check that error was logged (check both stdout and stderr)
        all_logs = job.logs.stdout + job.logs.stderr
        self.assertTrue(
            any("exceeded maximum runtime" in msg for msg in all_logs),
            f"Expected 'exceeded maximum runtime' in logs, got: {all_logs}",
        )

    def test_check_status_skip_final_states(self):
        """Test that jobs in final states are not re-checked."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Already Success",
            status=JobState.SUCCESS,
            started_at=timezone.now() - timedelta(minutes=5),
            finished_at=timezone.now(),
            task_id="some-task-id",
        )

        status_changed = job.check_status(force=True, save=True)

        self.assertFalse(status_changed)
        self.assertEqual(job.status, JobState.SUCCESS)

    def test_check_status_skip_recent_check(self):
        """Test that jobs checked recently are skipped unless forced."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Recent Check",
            status=JobState.STARTED,
            started_at=timezone.now() - timedelta(minutes=5),
            last_checked_at=timezone.now() - timedelta(seconds=30),  # 30 seconds ago
            task_id="some-task-id",
        )

        # Without force, should skip
        status_changed = job.check_status(force=False, save=True)
        self.assertFalse(status_changed)

        # With force, should check
        job.started_at = timezone.now() - timedelta(days=8)
        status_changed = job.check_status(force=True, save=True)
        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE)

    def test_check_status_updates_last_checked_at(self):
        """Test that last_checked_at is updated even when status doesn't change."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Update Timestamp",
            status=JobState.STARTED,
            started_at=timezone.now() - timedelta(minutes=5),
            task_id="some-task-id",
            last_checked_at=None,
        )

        self.assertIsNone(job.last_checked_at)
        job.check_status(force=True, save=True)
        self.assertIsNotNone(job.last_checked_at)

    def test_enqueue_syncs_status(self):
        """Test that enqueue() keeps status in sync."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Enqueue Sync",
        )

        # Enqueue the job
        job.enqueue()

        # Status and progress should be in sync
        self.assertEqual(job.status, job.progress.summary.status)

    def test_retry_syncs_status(self):
        """Test that retry() keeps status in sync."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            pipeline=self.pipeline,
            name="Test Job - Retry Sync",
            status=JobState.FAILURE,
        )

        job.retry(async_task=True)

        # Refresh to get latest status after retry() method completes
        job.refresh_from_db()

        # Status should have been updated and should be in sync
        # After retry() with async_task=True, it calls enqueue() which sets status to PENDING
        self.assertEqual(job.status, job.progress.summary.status)

    def test_cancel_syncs_status(self):
        """Test that cancel() keeps status in sync."""
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Cancel Sync",
            status=JobState.STARTED,
        )

        # Cancel the job (without task_id, so it goes to REVOKED)
        job.cancel()

        # Status should be REVOKED and in sync
        self.assertEqual(job.status, JobState.REVOKED)
        self.assertEqual(job.progress.summary.status, JobState.REVOKED)

    def test_status_checker_syncs_status(self):
        """Test that status checker keeps status in sync when marking as FAILURE."""
        from datetime import timedelta

        from django.utils import timezone

        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Test Job - Checker Sync",
            status=JobState.STARTED,
            started_at=timezone.now() - timedelta(days=8),  # Exceeds max runtime
            task_id="some-task",
        )

        # Check status - should mark as FAILURE
        status_changed = job.check_status(force=True, save=True)

        # Both should now be FAILURE and synced
        self.assertTrue(status_changed)
        self.assertEqual(job.status, JobState.FAILURE)
        self.assertEqual(job.progress.summary.status, JobState.FAILURE)


class TestCheckIncompleteJobsTask(TestCase):
    """
    Test the periodic task that checks all unfinished jobs.
    """

    def setUp(self):
        from django.core.cache import cache

        # Clear the lock before each test
        cache.delete("check_incomplete_jobs_lock")

        self.project = Project.objects.create(name="Periodic Check Test Project")
        self.pipeline = Pipeline.objects.create(
            name="Test ML pipeline",
            description="Test ML pipeline",
        )
        self.pipeline.projects.add(self.project)

    def tearDown(self):
        from django.core.cache import cache

        # Clear the lock after each test
        cache.delete("check_incomplete_jobs_lock")

    def test_check_incomplete_jobs_task(self):
        """Test the periodic task runs successfully."""
        from datetime import timedelta

        from django.utils import timezone

        from ami.jobs.tasks import check_incomplete_jobs

        # Create some test jobs in various states
        Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Job 1 - Started",
            status=JobState.STARTED,
            started_at=timezone.now() - timedelta(days=8),
            task_id="task-1",
        )
        Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Job 2 - Success",
            status=JobState.SUCCESS,
            finished_at=timezone.now(),
        )  # Should be skipped
        Job.objects.create(
            job_type_key=MLJob.key,
            project=self.project,
            name="Job 3 - Pending No Task",
            status=JobState.PENDING,
            scheduled_at=timezone.now() - timedelta(minutes=10),
            task_id=None,
        )

        result = check_incomplete_jobs()

        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(int(result["checked"]), 2)  # Should check jobs 1 and 3
        self.assertGreaterEqual(int(result["updated"]), 2)  # Should update both to FAILURE

    def test_check_incomplete_jobs_lock(self):
        """Test that concurrent executions are prevented by locking."""
        from django.core.cache import cache

        from ami.jobs.tasks import check_incomplete_jobs

        # Set the lock manually
        cache.set("check_incomplete_jobs_lock", "locked", 300)

        result = check_incomplete_jobs()

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "already_running")

    def test_check_incomplete_jobs_no_jobs(self):
        """Test the task handles empty job list gracefully."""
        from ami.jobs.tasks import check_incomplete_jobs

        result = check_incomplete_jobs()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["updated"], 0)


class TestWorkerAvailability(TestCase):
    """
    Test the worker availability checking functions.
    """

    def test_check_celery_workers_available(self):
        """Test that worker availability check returns a tuple."""
        from ami.jobs.status import check_celery_workers_available

        workers_available, worker_count = check_celery_workers_available()

        self.assertIsInstance(workers_available, bool)
        self.assertIsInstance(worker_count, int)

    def test_check_celery_workers_available_cached(self):
        """Test that cached version returns same result as uncached."""
        import time

        from ami.jobs.status import check_celery_workers_available, check_celery_workers_available_cached

        # Clear cache
        check_celery_workers_available_cached.cache_clear()

        timestamp = int(time.time() / 60)
        cached_result = check_celery_workers_available_cached(timestamp)
        direct_result = check_celery_workers_available()

        self.assertEqual(cached_result, direct_result)
