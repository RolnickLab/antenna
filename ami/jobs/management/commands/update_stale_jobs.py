from celery import states
from celery.result import AsyncResult
from django.core.management.base import BaseCommand
from django.utils import timezone

from ami.jobs.models import Job, JobState


class Command(BaseCommand):
    help = "Update the status of all jobs that are not in a final state and have not been updated in the last X hours."

    # Add argument for the number of hours to consider a job stale
    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=Job.FAILED_CUTOFF_HOURS,
            help="Number of hours to consider a job stale",
        )

    def handle(self, *args, **options):
        stale_jobs = Job.objects.filter(
            status__in=JobState.running_states(),
            updated_at__lt=timezone.now() - timezone.timedelta(hours=options["hours"]),
        )

        for job in stale_jobs:
            task = AsyncResult(job.task_id) if job.task_id else None
            if task:
                job.update_status(task.state, save=False)
                job.save()
                self.stdout.write(self.style.SUCCESS(f"Updated status of job {job.pk} to {task.state}"))
            else:
                self.stdout.write(self.style.WARNING(f"Job {job.pk} has no associated task, setting status to FAILED"))
                job.update_status(states.FAILURE, save=False)
                job.save()
