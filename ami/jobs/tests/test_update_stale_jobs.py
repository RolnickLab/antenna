from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from ami.jobs.models import Job, JobDispatchMode, JobState, MLJob, TrainClassifierJob
from ami.jobs.tasks import check_stale_jobs
from ami.main.models import Project


class CheckStaleJobsTest(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Stale jobs test project")

    def _create_job(self, status=JobState.STARTED, minutes_ago=120, task_id=None, job_type=None):
        job = Job.objects.create(
            project=self.project,
            name=f"Test job {status}",
            status=status,
            job_type_key=(job_type or MLJob).key,
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

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_skips_created_but_unstarted_jobs(self, mock_cleanup):
        """A job created but never enqueued is left alone regardless of age.

        Jobs can be pre-configured and started later, so a CREATED job has no
        Celery task and no async resources to reconcile. The staleness cutoff
        (measured against ``updated_at``) does not apply to it — it waits in
        CREATED until a user starts it. See #1354.
        """
        job = self._create_job(status=JobState.CREATED, minutes_ago=300)

        results = check_stale_jobs()

        self.assertEqual(results, [])
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.CREATED.value)
        mock_cleanup.assert_not_called()


class JobTypesThatWaitForACallbackTest(TestCase):
    """
    A training job goes quiet on purpose.

    It hands the work to a processing service and waits to be called back, so nothing
    touches it in the meantime: its progress messages go to the log table, not to the job
    row. The stale-job check reads that silence as a dead job and finishes it with no head
    registered, and the real callback is then refused because the job is already in a final
    state. Any run longer than the ordinary threshold died this way.
    """

    def setUp(self):
        self.project = Project.objects.create(name="Callback waiting project")

    def _job(self, job_type, minutes_ago):
        job = Job.objects.create(
            project=self.project,
            name="Waiting",
            status=JobState.STARTED,
            job_type_key=job_type.key,
        )
        Job.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(minutes=minutes_ago))
        job.refresh_from_db()
        return job

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_a_training_job_is_left_alone_while_its_callback_can_still_arrive(self, mock_cleanup):
        job = self._job(TrainClassifierJob, minutes_ago=120)

        results = check_stale_jobs()

        self.assertEqual(results, [])
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.STARTED.value)
        mock_cleanup.assert_not_called()

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_a_training_job_is_revoked_once_its_callback_can_no_longer_arrive(self, mock_cleanup):
        """The token authorising the callback expires, so past that the job cannot finish."""
        job = self._job(TrainClassifierJob, minutes_ago=TrainClassifierJob.stalled_after_minutes + 60)

        results = check_stale_jobs()

        self.assertEqual([r["action"] for r in results], ["revoked"])
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.REVOKED.value)

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_an_ordinary_job_still_goes_at_the_usual_threshold(self, mock_cleanup):
        """The longer wait is only for job types that say they wait for a callback."""
        job = self._job(MLJob, minutes_ago=120)

        results = check_stale_jobs()

        self.assertEqual([r["action"] for r in results], ["revoked"])
        job.refresh_from_db()
        self.assertEqual(job.status, JobState.REVOKED.value)
