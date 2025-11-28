from django.core.management.base import BaseCommand
from django.utils import timezone

from ami.jobs.models import Job, JobState


class Command(BaseCommand):
    help = (
        "Update the status of all jobs that are not in a final state "
        "and have not been updated in the last X hours. "
        "\n\nNOTE: This is now handled automatically by the periodic task 'check_unfinished_jobs'. "
        "This command is kept for manual intervention when needed."
    )

    # Add argument for the number of hours to consider a job stale
    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=Job.FAILED_CUTOFF_HOURS,
            help="Number of hours to consider a job stale",
        )
        parser.add_argument(
            "--no-retry",
            action="store_true",
            help="Disable automatic retry of disappeared tasks",
        )

    def handle(self, *args, **options):
        stale_jobs = Job.objects.filter(
            status__in=JobState.running_states(),
            updated_at__lt=timezone.now() - timezone.timedelta(hours=options["hours"]),
        )

        total = stale_jobs.count()
        self.stdout.write(f"Found {total} stale jobs to check...")

        updated_count = 0
        for job in stale_jobs:
            try:
                status_changed = job.check_status(force=False, save=True, auto_retry=not options["no_retry"])
                if status_changed:
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f"✓ Job {job.pk} status updated to {job.status}"))
                else:
                    self.stdout.write(self.style.WARNING(f"○ Job {job.pk} status unchanged ({job.status})"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Error checking job {job.pk}: {e}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Completed: {updated_count} of {total} jobs updated"))
