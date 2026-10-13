from django.core.management.base import BaseCommand

from ami.jobs.models import Job
from ami.jobs.tasks import check_stale_jobs


class Command(BaseCommand):
    help = "Revoke stale jobs that have not been updated within the cutoff period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=Job.STALLED_JOBS_MAX_MINUTES,
            help="Minutes since last update to consider a job stale (default: %(default)s)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )

    def handle(self, *args, **options):
        results = check_stale_jobs(minutes=options["minutes"], dry_run=options["dry_run"])

        if not results:
            self.stdout.write("No stale jobs found.")
            return

        prefix = "[dry-run] " if options["dry_run"] else ""
        for r in results:
            if r["action"] == "updated":
                self.stdout.write(
                    self.style.SUCCESS(f"{prefix}Job {r['job_id']}: updated to {r['state']} (from Celery)")
                )
            else:
                self.stdout.write(self.style.WARNING(f"{prefix}Job {r['job_id']}: revoked (no known Celery state)"))
