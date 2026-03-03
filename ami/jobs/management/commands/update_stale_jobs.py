from celery import states
from celery.result import AsyncResult
from django.core.management.base import BaseCommand
from django.utils import timezone

from ami.jobs.models import Job, JobState
from ami.jobs.tasks import cleanup_async_job_if_needed

# Celery returns PENDING for tasks it has no record of.
# These are the states that indicate a real, known task status.
KNOWN_CELERY_STATES = frozenset(states.ALL_STATES) - {states.PENDING}


class Command(BaseCommand):
    help = "Revoke stale jobs that have not been updated within the cutoff period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=Job.FAILED_CUTOFF_HOURS,
            help="Number of hours to consider a job stale (default: %(default)s)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timezone.timedelta(hours=options["hours"])
        stale_jobs = Job.objects.filter(
            status__in=JobState.running_states(),
            updated_at__lt=cutoff,
        )

        if not stale_jobs.exists():
            self.stdout.write("No stale jobs found.")
            return

        for job in stale_jobs:
            celery_state = None
            if job.task_id:
                celery_state = AsyncResult(job.task_id).state

            if celery_state in KNOWN_CELERY_STATES:
                # Celery has a real status for this task — use it
                if options["dry_run"]:
                    self.stdout.write(f"  [dry-run] Job {job.pk}: would update to {celery_state} (from Celery)")
                    continue
                job.update_status(celery_state, save=False)
                job.save()
                self.stdout.write(self.style.SUCCESS(f"Job {job.pk}: updated to {celery_state} (from Celery)"))
            else:
                # No task_id, or Celery has no record (returns PENDING) — revoke
                if options["dry_run"]:
                    self.stdout.write(f"  [dry-run] Job {job.pk} ({job.status}): would revoke and clean up")
                    continue
                job.update_status(JobState.REVOKED, save=False)
                job.finished_at = timezone.now()
                job.save()
                cleanup_async_job_if_needed(job)
                self.stdout.write(self.style.WARNING(f"Job {job.pk}: revoked (no known Celery state)"))
