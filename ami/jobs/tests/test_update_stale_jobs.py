from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from ami.jobs.models import Job, JobDispatchMode, JobState
from ami.jobs.tasks import check_stale_jobs
from ami.main.models import Project


class CheckStaleJobsTest(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Stale jobs test project")

    def _create_job(self, status=JobState.STARTED, minutes_ago=120, task_id=None):
        job = Job.objects.create(
            project=self.project,
            name=f"Test job {status}",
            status=status,
        )
        Job.objects.filter(pk=job.pk).update(
            updated_at=timezone.now() - timedelta(minutes=minutes_ago),
        )
        if task_id is not None:
            Job.objects.filter(pk=job.pk).update(task_id=task_id)
        job.refresh_from_db()
        return job

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_dry_run(self, mock_cleanup):
        """Dry run returns results without modifying jobs."""
        job = self._create_job(status=JobState.STARTED)

        results = check_stale_jobs(dry_run=True)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "revoked")
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.STARTED.value)
        mock_cleanup.assert_not_called()

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_revokes_stale_job(self, mock_cleanup):
        """Stale job without a known Celery state is revoked and cleaned up."""
        job = self._create_job(status=JobState.STARTED)

        results = check_stale_jobs()

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["action"], "revoked")
        self.assertEqual(result["previous_status"], JobState.STARTED)
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.REVOKED.value)
        self.assertIsNotNone(job.finished_at)
        mock_cleanup.assert_called_once_with(job)

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    @patch("celery.result.AsyncResult")
    def test_updates_status_from_known_celery_state(self, mock_async_result, mock_cleanup):
        """Stale job with a terminal Celery state is updated (not revoked)."""
        from celery import states

        mock_async_result.return_value.state = states.FAILURE
        job = self._create_job(status=JobState.STARTED, task_id="some-celery-task-id")

        results = check_stale_jobs()

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["action"], "updated")
        self.assertEqual(result["state"], states.FAILURE)
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.FAILURE.value)
        self.assertIsNotNone(job.finished_at)
        mock_cleanup.assert_called_once_with(job)

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    @patch("celery.result.AsyncResult")
    def test_revokes_success_with_incomplete_progress(self, mock_async_result, mock_cleanup):
        """async_api job where Celery reports SUCCESS but progress is incomplete is revoked."""
        from celery import states

        mock_async_result.return_value.state = states.SUCCESS
        job = self._create_job(status=JobState.STARTED, task_id="some-celery-task-id")
        Job.objects.filter(pk=job.pk).update(dispatch_mode=JobDispatchMode.ASYNC_API)
        job.refresh_from_db()
        # job.progress.is_complete() returns False by default (no stages completed)

        results = check_stale_jobs()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "revoked")
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.REVOKED.value)
        mock_cleanup.assert_called_once_with(job)

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    @patch("celery.result.AsyncResult")
    def test_revokes_when_celery_lookup_fails(self, mock_async_result, mock_cleanup):
        """Job is revoked if Celery state lookup raises an exception."""
        mock_async_result.side_effect = ConnectionError("broker down")
        job = self._create_job(status=JobState.STARTED, task_id="unreachable-task")

        results = check_stale_jobs()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["action"], "revoked")
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.REVOKED.value)
        mock_cleanup.assert_called_once_with(job)

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_skips_recent_and_final_state_jobs(self, mock_cleanup):
        """Recent jobs and jobs in final states are not touched."""
        self._create_job(status=JobState.STARTED, minutes_ago=5)  # recent
        self._create_job(status=JobState.SUCCESS, minutes_ago=300)  # final state

        results = check_stale_jobs()

        self.assertEqual(results, [])
        mock_cleanup.assert_not_called()
