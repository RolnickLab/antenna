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

    def _create_stale_job(self, status=JobState.STARTED, minutes_ago=120):
        job = Job.objects.create(project=self.project, name="stale", status=status)
        Job.objects.filter(pk=job.pk).update(updated_at=timezone.now() - timedelta(minutes=minutes_ago))
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
        # Zombie-stream sub-check defaults: no streams to inspect, no drains.
        instance.list_job_stream_snapshots = AsyncMock(return_value=[])
        instance.populate_redelivered_counts = AsyncMock(return_value=None)
        instance.delete_consumer = AsyncMock(return_value=True)
        instance.delete_stream = AsyncMock(return_value=True)
        # Lost-images sub-check default: no consumer state available (e.g. no
        # async_api stale jobs). Individual tests override when exercising the
        # reconciler path.
        instance.get_consumer_state = AsyncMock(return_value=None)
        return instance

    def test_reports_both_sub_check_results(self, mock_manager_cls, _mock_cleanup):
        self._create_stale_job()
        self._create_stale_job()
        self._stub_manager(mock_manager_cls)

        result = jobs_health_check()

        self.assertEqual(
            result,
            {
                "lost_images": _empty_check_dict(),
                "stale_jobs": {"checked": 2, "fixed": 2, "unfixable": 0},
                "running_job_snapshots": _empty_check_dict(),
                "zombie_streams": _empty_check_dict(),
            },
        )

    def test_idle_deployment_returns_all_zeros(self, mock_manager_cls, _mock_cleanup):
        # No stale jobs, no running async jobs.
        self._create_stale_job(minutes_ago=5)  # recent — not stale
        self._stub_manager(mock_manager_cls)

        self.assertEqual(
            jobs_health_check(),
            {
                "lost_images": _empty_check_dict(),
                "stale_jobs": _empty_check_dict(),
                "running_job_snapshots": _empty_check_dict(),
                "zombie_streams": _empty_check_dict(),
            },
        )

    def test_snapshots_each_running_async_job(self, mock_manager_cls, _mock_cleanup):
        job_a = self._create_async_job()
        job_b = self._create_async_job()
        instance = self._stub_manager(mock_manager_cls)

        result = jobs_health_check()

        self.assertEqual(result["running_job_snapshots"], {"checked": 2, "fixed": 0, "unfixable": 0})
        # Observation-only contract: the snapshot sub-check must never report
        # ``fixed > 0`` since it does not mutate state. Lock this in explicitly
        # so a future refactor that accidentally increments ``fixed`` breaks
        # this assertion rather than silently shipping.
        self.assertEqual(result["running_job_snapshots"]["fixed"], 0)
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

    def test_sub_check_exception_does_not_block_the_other(self, mock_manager_cls, _mock_cleanup):
        # One stale job to prove the reconciler would have had work; the
        # snapshot sub-check raises and must not prevent the stale-jobs
        # sub-check from running and reporting its own result.
        self._create_stale_job()
        self._stub_manager(mock_manager_cls)

        with patch(
            "ami.jobs.tasks._run_running_job_snapshot_check",
            side_effect=RuntimeError("pretend the observation check blew up"),
        ):
            result = jobs_health_check()

        # Stale-jobs sub-check completes normally and reports the reconciliation.
        self.assertEqual(result["stale_jobs"], {"checked": 1, "fixed": 1, "unfixable": 0})
        # Snapshot sub-check returns the `unfixable=1` sentinel on failure so
        # operators reading the task result see the check failed, not "nothing
        # to do."
        self.assertEqual(result["running_job_snapshots"], {"checked": 0, "fixed": 0, "unfixable": 1})

    def test_stale_jobs_fixed_counts_celery_updated_and_revoked_paths(self, mock_manager_cls, _mock_cleanup):
        # Two stale jobs in different reconciliation states: one has a Celery
        # task_id that returns a terminal state (counts as "updated from Celery"),
        # the other has no task_id and is forced to REVOKED. Both contribute to
        # `fixed` — this test guards against a refactor dropping one branch.
        from celery import states

        job_with_task = self._create_stale_job()
        job_with_task.task_id = "terminal-task"
        job_with_task.save(update_fields=["task_id"])
        self._create_stale_job()  # no task_id → revoked path
        self._stub_manager(mock_manager_cls)

        class _FakeAsyncResult:
            def __init__(self, task_id):
                self.state = states.SUCCESS if task_id == "terminal-task" else states.PENDING

        # `check_stale_jobs` imports AsyncResult locally from celery.result,
        # so patch at source rather than at the call site.
        with patch("celery.result.AsyncResult", _FakeAsyncResult):
            result = jobs_health_check()

        # checked == 2 (both stale), fixed == 2 (one per branch), unfixable == 0
        self.assertEqual(result["stale_jobs"], {"checked": 2, "fixed": 2, "unfixable": 0})

    def test_zombie_stream_drained_when_job_is_terminal_and_old(self, mock_manager_cls, _mock_cleanup):
        """An old stream whose Job is in a final state should be drained."""
        import datetime

        terminal_job = Job.objects.create(project=self.project, name="zombie owner", status=JobState.SUCCESS)
        instance = self._stub_manager(mock_manager_cls)
        old_ts = datetime.datetime.now() - datetime.timedelta(minutes=Job.ZOMBIE_STREAMS_MAX_AGE_MINUTES + 5)
        instance.list_job_stream_snapshots = AsyncMock(
            return_value=[
                {
                    "job_id": terminal_job.pk,
                    "stream_name": f"job_{terminal_job.pk}",
                    "created": old_ts,
                    "messages": 0,
                    "num_redelivered": 7,
                }
            ]
        )

        result = jobs_health_check()

        self.assertEqual(result["zombie_streams"], {"checked": 1, "fixed": 1, "unfixable": 0})
        instance.delete_consumer.assert_awaited_once_with(terminal_job.pk)
        instance.delete_stream.assert_awaited_once_with(terminal_job.pk)

    def test_zombie_stream_drained_when_job_is_missing_and_old(self, mock_manager_cls, _mock_cleanup):
        """An old stream whose Job row no longer exists should be drained."""
        import datetime

        instance = self._stub_manager(mock_manager_cls)
        old_ts = datetime.datetime.now() - datetime.timedelta(minutes=Job.ZOMBIE_STREAMS_MAX_AGE_MINUTES + 1)
        instance.list_job_stream_snapshots = AsyncMock(
            return_value=[
                {
                    "job_id": 987654,  # no Job row with this pk
                    "stream_name": "job_987654",
                    "created": old_ts,
                    "messages": 3,
                    "num_redelivered": 0,
                }
            ]
        )

        result = jobs_health_check()

        self.assertEqual(result["zombie_streams"], {"checked": 1, "fixed": 1, "unfixable": 0})
        instance.delete_stream.assert_awaited_once_with(987654)

    def test_zombie_stream_not_drained_when_below_age_threshold(self, mock_manager_cls, _mock_cleanup):
        """A fresh stream for a terminal job must NOT be drained (on_commit race guard)."""
        import datetime

        terminal_job = Job.objects.create(project=self.project, name="fresh zombie?", status=JobState.FAILURE)
        instance = self._stub_manager(mock_manager_cls)
        fresh_ts = datetime.datetime.now() - datetime.timedelta(minutes=1)
        instance.list_job_stream_snapshots = AsyncMock(
            return_value=[
                {
                    "job_id": terminal_job.pk,
                    "stream_name": f"job_{terminal_job.pk}",
                    "created": fresh_ts,
                    "messages": 0,
                    "num_redelivered": 0,
                }
            ]
        )

        result = jobs_health_check()

        self.assertEqual(result["zombie_streams"], {"checked": 1, "fixed": 0, "unfixable": 0})
        instance.delete_stream.assert_not_awaited()

    def test_zombie_stream_not_drained_when_job_still_running(self, mock_manager_cls, _mock_cleanup):
        """An old stream for a still-running job must NOT be drained."""
        import datetime

        running_job = Job.objects.create(project=self.project, name="still running", status=JobState.STARTED)
        instance = self._stub_manager(mock_manager_cls)
        old_ts = datetime.datetime.now() - datetime.timedelta(minutes=Job.ZOMBIE_STREAMS_MAX_AGE_MINUTES + 10)
        instance.list_job_stream_snapshots = AsyncMock(
            return_value=[
                {
                    "job_id": running_job.pk,
                    "stream_name": f"job_{running_job.pk}",
                    "created": old_ts,
                    "messages": 5,
                    "num_redelivered": 0,
                }
            ]
        )

        result = jobs_health_check()

        self.assertEqual(result["zombie_streams"], {"checked": 1, "fixed": 0, "unfixable": 0})
        instance.delete_stream.assert_not_awaited()

    def test_zombie_stream_drain_failure_counts_as_unfixable(self, mock_manager_cls, _mock_cleanup):
        """A drain that raises should be counted as unfixable without crashing the umbrella."""
        import datetime

        terminal_job = Job.objects.create(project=self.project, name="unfixable", status=JobState.SUCCESS)
        instance = self._stub_manager(mock_manager_cls)
        old_ts = datetime.datetime.now() - datetime.timedelta(minutes=Job.ZOMBIE_STREAMS_MAX_AGE_MINUTES + 2)
        instance.list_job_stream_snapshots = AsyncMock(
            return_value=[
                {
                    "job_id": terminal_job.pk,
                    "stream_name": f"job_{terminal_job.pk}",
                    "created": old_ts,
                    "messages": 0,
                    "num_redelivered": 0,
                }
            ]
        )
        instance.delete_consumer = AsyncMock(side_effect=RuntimeError("nats error"))

        result = jobs_health_check()

        self.assertEqual(result["zombie_streams"], {"checked": 1, "fixed": 0, "unfixable": 1})

    def test_zombie_stream_skipped_when_created_is_none(self, mock_manager_cls, _mock_cleanup):
        """A snapshot with created=None must be skipped (unfixable), never drained.

        The age guard exists to protect streams whose Job row hasn't committed yet.
        A missing/unparseable timestamp means we cannot determine age, so the safe
        default is to leave the stream alone and report it as unfixable.
        """
        instance = self._stub_manager(mock_manager_cls)
        instance.list_job_stream_snapshots = AsyncMock(
            return_value=[
                {
                    "job_id": 111222,
                    "stream_name": "job_111222",
                    "created": None,
                    "messages": 2,
                    "num_redelivered": None,
                }
            ]
        )

        result = jobs_health_check()

        self.assertEqual(result["zombie_streams"], {"checked": 1, "fixed": 0, "unfixable": 1})
        instance.delete_consumer.assert_not_awaited()
        instance.delete_stream.assert_not_awaited()

    def test_list_job_stream_snapshots_raises_on_nats_error_payload(self, mock_manager_cls, _mock_cleanup):
        """list_job_stream_snapshots must raise (not return []) when the NATS server responds with an error.

        Returning [] would mask an outage — the caller would silently interpret
        "zero zombies" when NATS is actually unavailable.
        """
        import nats.errors

        instance = self._stub_manager(mock_manager_cls)
        instance.list_job_stream_snapshots = AsyncMock(
            side_effect=nats.errors.Error("NATS STREAM.LIST error 503: no responders available for request")
        )

        result = jobs_health_check()

        # _safe_run_sub_check catches the exception and records unfixable=1.
        self.assertEqual(result["zombie_streams"], {"checked": 0, "fixed": 0, "unfixable": 1})
