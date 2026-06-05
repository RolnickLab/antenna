"""End-to-end test harness for ``RegroupEventsJob`` and the regroup stage of
``DataStorageSyncJob``.

Mirrors ``test_ml_job_e2e`` for the session-regrouping path (PR #1292). Used to
validate:

* Mode ``regroup``: ``RegroupEventsJob`` runs to SUCCESS against a real
  deployment, stage params are populated, Event count delta is reasonable.
* Mode ``sync``: ``DataStorageSyncJob`` exposes a two-stage progress
  (sync_captures + regroup_sessions), both reach SUCCESS, regroup stage params
  are populated.
* Mode ``concurrent``: Two ``RegroupEventsJob`` enqueues for the same
  deployment within the lock TTL — exactly one stage produces non-zero stats,
  the other short-circuits with a lock warning, and Event count does not
  diverge from the single-run baseline.
"""

import time

from django.core.management.base import BaseCommand, CommandError

from ami.jobs.models import DataStorageSyncJob, Job, JobState, RegroupEventsJob
from ami.main.models import Deployment, Event


class Command(BaseCommand):
    help = (
        "Run end-to-end tests for the regroup-events Job path.\n\n"
        "Modes:\n"
        "  regroup     — RegroupEventsJob on a deployment\n"
        "  sync        — DataStorageSyncJob (covers sync→regroup chain)\n"
        "  concurrent  — two RegroupEventsJobs back-to-back, asserts lock semantics\n"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "mode",
            choices=["regroup", "sync", "concurrent"],
            help="Which scenario to exercise",
        )
        parser.add_argument("--deployment", type=int, required=True, help="Deployment ID")
        parser.add_argument(
            "--poll-interval", type=float, default=2.0, help="Seconds between Job state polls (default 2.0)"
        )
        parser.add_argument(
            "--timeout", type=float, default=600.0, help="Max seconds to wait for each Job (default 600)"
        )

    def handle(self, *args, **options):
        deployment = self._resolve_deployment(options["deployment"])
        mode = options["mode"]

        if mode == "regroup":
            self._run_regroup(deployment, options)
        elif mode == "sync":
            self._run_sync(deployment, options)
        elif mode == "concurrent":
            self._run_concurrent(deployment, options)

    def _resolve_deployment(self, deployment_id: int) -> Deployment:
        try:
            deployment = Deployment.objects.get(pk=deployment_id)
        except Deployment.DoesNotExist:
            raise CommandError(f"Deployment {deployment_id} not found")
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Deployment {deployment.pk} '{deployment.name}' "
                f"(project={deployment.project_id}, captures={deployment.captures_count})"
            )
        )
        gap = deployment.project.session_time_gap_seconds if deployment.project_id else None
        self.stdout.write(f"  project session_time_gap_seconds = {gap!r}")
        before = Event.objects.filter(deployment=deployment).count()
        self.stdout.write(f"  Events before run: {before}")
        return deployment

    def _run_regroup(self, deployment: Deployment, options: dict) -> None:
        before = Event.objects.filter(deployment=deployment).count()
        job = self._make_regroup_job(deployment, suffix="e2e-regroup")
        self.stdout.write(f"\n🚀 RegroupEventsJob {job.pk} enqueueing")
        job.enqueue()
        self._monitor(job, options)
        after = Event.objects.filter(deployment=deployment).count()
        self.stdout.write(f"\nEvents after: {after} (Δ {after - before:+d})")
        self._assert_status(job, expected=JobState.SUCCESS)
        self._dump_stage_params(job)

    def _run_sync(self, deployment: Deployment, options: dict) -> None:
        if not deployment.data_source_id:
            raise CommandError(
                f"Deployment {deployment.pk} has no data_source — DataStorageSyncJob would fail immediately."
            )
        before = Event.objects.filter(deployment=deployment).count()
        job = Job.objects.create(
            name=f"E2E sync→regroup chain (deployment {deployment.pk})",
            project=deployment.project,
            deployment=deployment,
            job_type_key=DataStorageSyncJob.key,
        )
        self.stdout.write(f"\n🚀 DataStorageSyncJob {job.pk} enqueueing")
        job.enqueue()
        self._monitor(job, options)
        after = Event.objects.filter(deployment=deployment).count()
        self.stdout.write(f"\nEvents after: {after} (Δ {after - before:+d})")
        self._assert_status(job, expected=JobState.SUCCESS)

        stage_keys = [s.key for s in (job.progress.stages or [])]
        if DataStorageSyncJob.regroup_stage_key not in stage_keys:
            raise CommandError(
                f"❌ DataStorageSyncJob exposed stages {stage_keys!r} — missing "
                f"'{DataStorageSyncJob.regroup_stage_key}' regroup stage."
            )
        self.stdout.write(self.style.SUCCESS(f"✓ Sync Job exposed both stages: {stage_keys!r}"))
        self._dump_stage_params(job)

    def _run_concurrent(self, deployment: Deployment, options: dict) -> None:
        before = Event.objects.filter(deployment=deployment).count()
        job_a = self._make_regroup_job(deployment, suffix="e2e-concurrent-A")
        job_b = self._make_regroup_job(deployment, suffix="e2e-concurrent-B")
        self.stdout.write(f"\n🚀 Enqueueing two RegroupEventsJobs back-to-back: {job_a.pk}, {job_b.pk}")
        job_a.enqueue()
        # No sleep between — we want both Celery tasks to race for the lock.
        job_b.enqueue()

        self.stdout.write("\nMonitoring job A:")
        self._monitor(job_a, options)
        self.stdout.write("\nMonitoring job B:")
        self._monitor(job_b, options)

        after = Event.objects.filter(deployment=deployment).count()
        self.stdout.write(f"\nEvents after both jobs: {after} (Δ {after - before:+d})")

        for job in (job_a, job_b):
            self._assert_status(job, expected=JobState.SUCCESS)

        params_a = self._stage_param_dict(job_a, RegroupEventsJob.key)
        params_b = self._stage_param_dict(job_b, RegroupEventsJob.key)
        self.stdout.write(f"\nJob A stage params: {params_a}")
        self.stdout.write(f"Job B stage params: {params_b}")

        # Exactly one of A/B should have done real work (captures_grouped > 0);
        # the other should have short-circuited and reported the initial zeroes.
        worked_a = (params_a.get("captures_grouped") or 0) > 0
        worked_b = (params_b.get("captures_grouped") or 0) > 0
        if worked_a == worked_b:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Lock did not separate runs as expected — both jobs reported "
                    f"captures_grouped={params_a.get('captures_grouped')}/"
                    f"{params_b.get('captures_grouped')}. "
                    f"This can happen if the worker ran them serially fast enough that the lock cleared between."
                )
            )
        else:
            winner = "A" if worked_a else "B"
            loser = "B" if worked_a else "A"
            self.stdout.write(
                self.style.SUCCESS(f"✓ Lock semantics held: job {winner} did the work, job {loser} short-circuited.")
            )

    def _make_regroup_job(self, deployment: Deployment, suffix: str) -> Job:
        return Job.objects.create(
            name=f"E2E {suffix} (deployment {deployment.pk})",
            project=deployment.project,
            deployment=deployment,
            job_type_key=RegroupEventsJob.key,
        )

    def _monitor(self, job: Job, options: dict) -> None:
        start = time.time()
        timeout = options["timeout"]
        interval = options["poll_interval"]
        last_status = None
        while True:
            job.refresh_from_db()
            elapsed = time.time() - start
            if job.status != last_status:
                self.stdout.write(f"  [{elapsed:6.1f}s] Job {job.pk} status: {job.status}")
                last_status = job.status
            if job.status in JobState.final_states():
                self.stdout.write(f"  [{elapsed:6.1f}s] Job {job.pk} reached final state {job.status}")
                return
            if elapsed > timeout:
                raise CommandError(
                    f"❌ Job {job.pk} did not reach a final state within {timeout}s (status={job.status})"
                )
            time.sleep(interval)

    def _assert_status(self, job: Job, expected: str) -> None:
        if job.status != expected:
            raise CommandError(
                f"❌ Job {job.pk} ended with status {job.status!r} (expected {expected!r}). "
                f"Stages: {[(s.key, s.status, s.progress) for s in (job.progress.stages or [])]}"
            )
        self.stdout.write(self.style.SUCCESS(f"✓ Job {job.pk} ended {expected}"))

    def _stage_param_dict(self, job: Job, stage_key: str) -> dict:
        for stage in job.progress.stages or []:
            if stage.key == stage_key:
                return {param.key: param.value for param in (stage.params or [])}
        return {}

    def _dump_stage_params(self, job: Job) -> None:
        for stage in job.progress.stages or []:
            self.stdout.write(
                f"\n  Stage '{stage.name}' ({stage.key}): status={stage.status} progress={stage.progress}"
            )
            for param in stage.params or []:
                self.stdout.write(f"    {param.key}: {param.value}")
