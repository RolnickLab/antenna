import logging
import sys

from django.core.management.base import BaseCommand, CommandError

from ami.jobs.models import Job

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process a job directly for testing purposes"

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=int, help="Job ID to process")
        parser.add_argument("--sync", action="store_true", help="Run directly instead of using Celery")
        parser.add_argument("--debug", action="store_true", help="Show more detailed logs")

    def handle(self, *args, **options):
        job_id = options["job_id"]
        sync_mode = options["sync"]
        debug_mode = options["debug"]

        if debug_mode:
            # Set up console logger
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logging.getLogger("ami").setLevel(logging.DEBUG)
            logging.getLogger("ami").addHandler(handler)

        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise CommandError(f"Job {job_id} does not exist")

        self.stdout.write(self.style.SUCCESS(f'Processing job {job} ({"sync" if sync_mode else "async"} mode)'))

        if sync_mode:
            # Run directly without Celery
            self.stdout.write("Running job synchronously without Celery...")
            from ami.jobs.tasks import initialize_job as initialize_job_task

            # Use apply() to run synchronously but properly handle Celery's class methods
            result = initialize_job_task.apply(kwargs={"job_id": job_id}, throw=True)
            self.stdout.write(self.style.SUCCESS(f"Job {job_id} completed in sync mode with result: {result.get()}"))
        else:
            # Queue via Celery
            from ami.jobs.tasks import initialize_job as initialize_job_task

            task = initialize_job_task.delay(job_id=job_id)
            self.stdout.write(self.style.SUCCESS(f"Job {job_id} queued as task {task.id}"))
