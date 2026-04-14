from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.utils import timezone

from ami.jobs.models import Job, JobDispatchMode, JobState
from ami.jobs.tasks import jobs_health_check, log_running_async_job_stats
from ami.main.models import Project


class JobsHealthCheckTest(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Beat schedule test project")

    def _create_stale_job(self, status=JobState.STARTED, hours_ago=100):
        job = Job.objects.create(project=self.project, name="stale", status=status)
        Job.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(hours=hours_ago))
        job.refresh_from_db()
        return job

    @patch("ami.jobs.tasks.cleanup_async_job_if_needed")
    def test_returns_nested_summary_counts(self, _mock_cleanup):
        self._create_stale_job()
        self._create_stale_job()
        result = jobs_health_check()
        self.assertEqual(result, {"stale_jobs": {"checked": 2, "fixed": 2, "unfixable": 0}})

    def test_no_stale_jobs_returns_zero_summary(self):
        self._create_stale_job(hours_ago=1)  # recent — not stale
        self.assertEqual(
            jobs_health_check(),
            {"stale_jobs": {"checked": 0, "fixed": 0, "unfixable": 0}},
        )


class LogRunningAsyncJobStatsTest(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Async snapshot test project")

    def _create_async_job(self, status=JobState.STARTED):
        job = Job.objects.create(project=self.project, name=f"async {status}", status=status)
        Job.objects.filter(pk=job.pk).update(dispatch_mode=JobDispatchMode.ASYNC_API)
        job.refresh_from_db()
        return job

    def test_no_running_jobs_short_circuits(self):
        # A celery job with async dispatch but a final status should be skipped.
        self._create_async_job(status=JobState.SUCCESS)
        self.assertEqual(log_running_async_job_stats(), {"checked": 0})

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_snapshots_each_running_async_job(self, mock_manager_cls):
        job_a = self._create_async_job()
        job_b = self._create_async_job()

        instance = mock_manager_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.log_consumer_stats_snapshot = AsyncMock()

        result = log_running_async_job_stats()

        self.assertEqual(result, {"checked": 2})
        snapshots = [call.args[0] for call in instance.log_consumer_stats_snapshot.await_args_list]
        self.assertCountEqual(snapshots, [job_a.pk, job_b.pk])

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_one_job_failure_does_not_block_others(self, mock_manager_cls):
        job_ok = self._create_async_job()
        job_broken = self._create_async_job()

        instance = mock_manager_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)

        calls = []

        async def _snapshot(job_id):
            calls.append(job_id)
            if job_id == job_broken.pk:
                raise RuntimeError("nats down for this one")

        instance.log_consumer_stats_snapshot = AsyncMock(side_effect=_snapshot)

        result = log_running_async_job_stats()
        self.assertEqual(result, {"checked": 2})
        self.assertIn(job_ok.pk, calls)
        self.assertIn(job_broken.pk, calls)

    @patch("ami.jobs.tasks.TaskQueueManager")
    def test_shared_connection_failure_falls_back_to_per_job(self, mock_manager_cls):
        job_a = self._create_async_job()
        job_b = self._create_async_job()

        instance = mock_manager_cls.return_value
        # First __aenter__ (shared path) blows up; subsequent ones (per-job
        # fallback) succeed. Simulates a bug that only affects the shared path.
        instance.__aenter__ = AsyncMock(
            side_effect=[RuntimeError("shared path broken"), instance, instance],
        )
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.log_consumer_stats_snapshot = AsyncMock()

        result = log_running_async_job_stats()

        self.assertEqual(result, {"checked": 2})
        # Shared attempt + one fresh manager per job = 3 __aenter__ calls total.
        self.assertEqual(instance.__aenter__.await_count, 3)
        snapshots = [call.args[0] for call in instance.log_consumer_stats_snapshot.await_args_list]
        self.assertCountEqual(snapshots, [job_a.pk, job_b.pk])

    def test_non_async_jobs_skipped(self):
        job = Job.objects.create(project=self.project, name="sync job", status=JobState.STARTED)
        # default dispatch_mode should not be ASYNC_API
        self.assertNotEqual(job.dispatch_mode, JobDispatchMode.ASYNC_API)
        self.assertEqual(log_running_async_job_stats(), {"checked": 0})
