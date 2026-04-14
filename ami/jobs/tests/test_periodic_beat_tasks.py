from datetime import timedelta
from unittest.mock import AsyncMock, patch

from django.test import TestCase
from django.utils import timezone

from ami.jobs.models import Job, JobDispatchMode, JobState
from ami.jobs.tasks import jobs_health_check
from ami.main.models import Project


def _empty_check_dict() -> dict:
    return {"checked": 0, "fixed": 0, "unfixable": 0}


@patch("ami.jobs.tasks.cleanup_async_job_if_needed")
@patch("ami.jobs.tasks.TaskQueueManager")
class JobsHealthCheckTest(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Beat schedule test project")

    def _create_stale_job(self, status=JobState.STARTED, hours_ago=100):
        job = Job.objects.create(project=self.project, name="stale", status=status)
        Job.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(hours=hours_ago))
        job.refresh_from_db()
        return job

    def _create_async_job(self, status=JobState.STARTED):
        job = Job.objects.create(project=self.project, name=f"async {status}", status=status)
        Job.objects.filter(pk=job.pk).update(dispatch_mode=JobDispatchMode.ASYNC_API)
        job.refresh_from_db()
        return job

    def _stub_manager(self, mock_manager_cls) -> AsyncMock:
        instance = mock_manager_cls.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.log_consumer_stats_snapshot = AsyncMock()
        return instance

    def test_reports_both_sub_check_results(self, mock_manager_cls, _mock_cleanup):
        self._create_stale_job()
        self._create_stale_job()
        self._stub_manager(mock_manager_cls)

        result = jobs_health_check()

        self.assertEqual(
            result,
            {
                "stale_jobs": {"checked": 2, "fixed": 2, "unfixable": 0},
                "running_job_snapshots": _empty_check_dict(),
            },
        )

    def test_idle_deployment_returns_all_zeros(self, mock_manager_cls, _mock_cleanup):
        # No stale jobs, no running async jobs.
        self._create_stale_job(hours_ago=1)  # recent — not stale
        self._stub_manager(mock_manager_cls)

        self.assertEqual(
            jobs_health_check(),
            {
                "stale_jobs": _empty_check_dict(),
                "running_job_snapshots": _empty_check_dict(),
            },
        )

    def test_snapshots_each_running_async_job(self, mock_manager_cls, _mock_cleanup):
        job_a = self._create_async_job()
        job_b = self._create_async_job()
        instance = self._stub_manager(mock_manager_cls)

        result = jobs_health_check()

        self.assertEqual(result["running_job_snapshots"], {"checked": 2, "fixed": 0, "unfixable": 0})
        snapshots = [call.args[0] for call in instance.log_consumer_stats_snapshot.await_args_list]
        self.assertCountEqual(snapshots, [job_a.pk, job_b.pk])

    def test_one_job_snapshot_failure_counts_as_unfixable(self, mock_manager_cls, _mock_cleanup):
        job_ok = self._create_async_job()
        job_broken = self._create_async_job()
        instance = self._stub_manager(mock_manager_cls)

        calls = []

        async def _snapshot(job_id):
            calls.append(job_id)
            if job_id == job_broken.pk:
                raise RuntimeError("nats down for this one")

        instance.log_consumer_stats_snapshot = AsyncMock(side_effect=_snapshot)

        result = jobs_health_check()

        # Both jobs were attempted; only the broken one failed.
        self.assertEqual(result["running_job_snapshots"], {"checked": 2, "fixed": 0, "unfixable": 1})
        self.assertIn(job_ok.pk, calls)
        self.assertIn(job_broken.pk, calls)

    def test_shared_connection_setup_failure_marks_all_unfixable(self, mock_manager_cls, _mock_cleanup):
        self._create_async_job()
        self._create_async_job()

        instance = mock_manager_cls.return_value
        instance.__aenter__ = AsyncMock(side_effect=RuntimeError("nats down"))
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.log_consumer_stats_snapshot = AsyncMock()

        result = jobs_health_check()

        # All running jobs are counted as unfixable for this tick; no
        # snapshots ran and the shared-connection error was swallowed.
        self.assertEqual(result["running_job_snapshots"], {"checked": 2, "fixed": 0, "unfixable": 2})
        instance.log_consumer_stats_snapshot.assert_not_awaited()

    def test_non_async_running_jobs_are_ignored_by_snapshot_check(self, mock_manager_cls, _mock_cleanup):
        job = Job.objects.create(project=self.project, name="sync job", status=JobState.STARTED)
        self.assertNotEqual(job.dispatch_mode, JobDispatchMode.ASYNC_API)
        instance = self._stub_manager(mock_manager_cls)

        result = jobs_health_check()

        self.assertEqual(result["running_job_snapshots"], _empty_check_dict())
        instance.log_consumer_stats_snapshot.assert_not_awaited()
