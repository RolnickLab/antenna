"""
Management command for testing and troubleshooting jobs and Celery tasks.

This command provides utilities to simulate various job/task issues for testing
the job status monitoring system.
"""

from celery.result import AsyncResult
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ami.jobs.models import Job, JobState, MLJob
from ami.main.models import Project


class Command(BaseCommand):
    help = """
    Utilities for testing and troubleshooting jobs and Celery tasks.

    Examples:
        # Check a specific job's status
        python manage.py debug_jobs --check-job 123

        # Remove a job's task from Celery (simulate disappeared task)
        python manage.py debug_jobs --remove-task 123

        # Corrupt a job's task_id (simulate bad data)
        python manage.py debug_jobs --corrupt-task 123

        # Check all unfinished jobs (run periodic task)
        python manage.py debug_jobs --check-all

        # List all unfinished jobs
        python manage.py debug_jobs --list-unfinished

        # Get detailed info about a job
        python manage.py debug_jobs --info 123

        # Create and run a 5-minute test job for project 1
        python manage.py debug_jobs --create-test-job 1

        # Create and run async (in background via Celery)
        python manage.py debug_jobs --create-test-job 1 --async
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--check-job",
            type=int,
            metavar="JOB_ID",
            help="Check status of a specific job by ID",
        )

        parser.add_argument(
            "--remove-task",
            type=int,
            metavar="JOB_ID",
            help="Remove a job's Celery task (simulates disappeared task)",
        )

        parser.add_argument(
            "--corrupt-task",
            type=int,
            metavar="JOB_ID",
            help="Corrupt a job's task_id (simulates bad data)",
        )

        parser.add_argument(
            "--check-all",
            action="store_true",
            help="Check all unfinished jobs without making changes (dry-run mode)",
        )

        parser.add_argument(
            "--update-all",
            action="store_true",
            help="Check and update all unfinished jobs (runs periodic task with save=True)",
        )

        parser.add_argument(
            "--list-unfinished",
            action="store_true",
            help="List all unfinished jobs",
        )

        parser.add_argument(
            "--info",
            type=int,
            metavar="JOB_ID",
            help="Get detailed information about a job",
        )

        parser.add_argument(
            "--create-test-job",
            type=int,
            metavar="PROJECT_ID",
            help="Create and run a long-running test job (5+ minutes) for the specified project",
        )

        parser.add_argument(
            "--async",
            action="store_true",
            dest="run_async",
            help="Run the created test job asynchronously (default: synchronous)",
        )

        parser.add_argument(
            "--no-retry",
            action="store_true",
            help="Disable automatic retry when checking status",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Force check even if job is in final state",
        )

    def handle(self, *args, **options):
        # Check which action to perform
        actions_taken = 0

        if options["check_job"]:
            self.check_job_status(options["check_job"], options)
            actions_taken += 1

        if options["remove_task"]:
            self.remove_task(options["remove_task"])
            actions_taken += 1

        if options["corrupt_task"]:
            self.corrupt_task(options["corrupt_task"])
            actions_taken += 1

        if options["check_all"]:
            self.check_all_jobs(dry_run=True)
            actions_taken += 1

        if options["update_all"]:
            self.check_all_jobs(dry_run=False)
            actions_taken += 1

        if options["list_unfinished"]:
            self.list_unfinished_jobs()
            actions_taken += 1

        if options["info"]:
            self.show_job_info(options["info"])
            actions_taken += 1

        if options["create_test_job"]:
            self.create_test_job(options["create_test_job"], options)
            actions_taken += 1

        if actions_taken == 0:
            self.stdout.write(self.style.WARNING("No action specified. Use --help to see available options."))

    def get_job(self, job_id: int) -> Job:
        """Get a job by ID or raise CommandError."""
        try:
            return Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise CommandError(f"Job {job_id} does not exist")

    def check_job_status(self, job_id: int, options: dict):
        """Check the status of a specific job."""
        job = self.get_job(job_id)

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Checking Job #{job_id}: {job.name}")
        self.stdout.write(f"{'='*60}\n")

        self.stdout.write(f"Current Status: {self.style.WARNING(job.status)}")
        self.stdout.write(f"Task ID: {job.task_id or '(none)'}")
        self.stdout.write(f"Scheduled: {job.scheduled_at or '(never)'}")
        self.stdout.write(f"Started: {job.started_at or '(never)'}")
        self.stdout.write(f"Finished: {job.finished_at or '(never)'}")
        self.stdout.write(f"Last Checked: {job.last_checked_at or '(never)'}")

        # Check Celery task if exists
        if job.task_id:
            self.stdout.write("\n--- Celery Task Info ---")
            try:
                task = AsyncResult(job.task_id)
                self.stdout.write(f"Celery Status: {task.status}")
                self.stdout.write(f"Task Ready: {task.ready()}")
                self.stdout.write(f"Task Successful: {task.successful() if task.ready() else 'N/A'}")
                if task.ready() and not task.successful():
                    self.stdout.write(f"Task Error: {task.result}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error querying Celery: {e}"))

        # Run check_status
        self.stdout.write("\n--- Running check_status() ---")
        try:
            status_changed = job.check_status(
                force=options.get("force", False), save=True, auto_retry=not options.get("no_retry", False)
            )

            job.refresh_from_db()

            if status_changed:
                self.stdout.write(self.style.SUCCESS(f"✓ Status changed to: {job.status}"))
            else:
                self.stdout.write(self.style.WARNING(f"○ Status unchanged: {job.status}"))

            self.stdout.write(f"\nFinal State:")
            self.stdout.write(f"  Status: {job.status}")
            self.stdout.write(f"  Finished: {job.finished_at or '(still running)'}")
            self.stdout.write(f"  Last Checked: {job.last_checked_at}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error checking status: {e}"))
            raise

    def remove_task(self, job_id: int):
        """Remove/revoke a job's Celery task to simulate disappeared task."""
        job = self.get_job(job_id)

        if not job.task_id:
            raise CommandError(f"Job {job_id} has no task_id")

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Removing Task for Job #{job_id}: {job.name}")
        self.stdout.write(f"{'='*60}\n")

        self.stdout.write(f"Current Status: {job.status}")
        self.stdout.write(f"Task ID: {job.task_id}")

        try:
            task = AsyncResult(job.task_id)
            self.stdout.write(f"Celery Status (before): {task.status}")

            # Revoke the task
            task.revoke(terminate=True)
            self.stdout.write(self.style.SUCCESS("✓ Task revoked"))

            # Forget the task (removes from result backend)
            task.forget()
            self.stdout.write(self.style.SUCCESS("✓ Task forgotten (removed from result backend)"))

            # Check status again
            task = AsyncResult(job.task_id)
            self.stdout.write(f"Celery Status (after): {task.status}")

            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠ Job status in database is still '{job.status}'. " f"Run --check-job {job_id} to update it."
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error removing task: {e}"))
            raise

    def corrupt_task(self, job_id: int):
        """Corrupt a job's task_id to simulate bad data."""
        job = self.get_job(job_id)

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Corrupting Task ID for Job #{job_id}: {job.name}")
        self.stdout.write(f"{'='*60}\n")

        old_task_id = job.task_id
        self.stdout.write(f"Old Task ID: {old_task_id or '(none)'}")

        # Generate a fake task_id
        import uuid

        fake_task_id = f"fake-task-{uuid.uuid4()}"

        job.task_id = fake_task_id
        job.save(update_fields=["task_id"], update_progress=False)

        self.stdout.write(f"New Task ID: {self.style.WARNING(fake_task_id)}")
        self.stdout.write(self.style.SUCCESS(f"✓ Task ID corrupted. This will simulate a disappeared task scenario."))

        self.stdout.write(self.style.WARNING(f"\n⚠ Run --check-job {job_id} to see how the system handles this."))

    def check_all_jobs(self, dry_run: bool = True):
        """Check all unfinished jobs, optionally without saving changes."""
        mode_label = "Dry-Run Mode (no changes will be saved)" if dry_run else "Update Mode (changes will be saved)"

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Checking All Unfinished Jobs - {mode_label}")
        self.stdout.write(f"{'='*60}\n")

        # Get all unfinished jobs, excluding CREATED jobs that have never been scheduled
        unfinished_jobs = (
            Job.objects.filter(status__in=JobState.running_states())
            .exclude(status=JobState.CREATED.value, scheduled_at__isnull=True)
            .order_by("-created_at")
        )
        unfinished_count = unfinished_jobs.count()

        self.stdout.write(f"Found {unfinished_count} unfinished jobs\n")

        if unfinished_count == 0:
            self.stdout.write(self.style.SUCCESS("✓ No unfinished jobs to check!"))
            return

        checked = 0
        updated = 0
        errors = 0

        for job in unfinished_jobs:
            try:
                self.stdout.write(f"Checking Job #{job.pk}: {job.name[:50]} ({job.status})")

                # Check status without saving in dry-run mode
                status_changed = job.check_status(force=False, save=not dry_run, auto_retry=not dry_run)

                checked += 1

                if status_changed:
                    job.refresh_from_db()
                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(f"  → Would change to: {job.status} (dry-run, not saved)")
                        )
                    else:
                        self.stdout.write(self.style.SUCCESS(f"  → Changed to: {job.status}"))
                    updated += 1
                else:
                    self.stdout.write("  → No change needed")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error: {e}"))
                errors += 1

        # Summary
        self.stdout.write("\n--- Summary ---")
        self.stdout.write(f"Total Unfinished: {unfinished_count}")
        self.stdout.write(f"Checked: {checked}")
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Would Update: {updated}"))
            self.stdout.write(self.style.NOTICE("\n💡 Use --update-all to actually save the changes"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated: {updated}"))

        if errors > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {errors}"))

    def list_unfinished_jobs(self):
        """List all unfinished jobs with their details."""
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("Unfinished Jobs")
        self.stdout.write(f"{'='*60}\n")

        # Exclude CREATED jobs that have never been scheduled (nothing to check)
        unfinished_jobs = (
            Job.objects.filter(status__in=JobState.running_states())
            .exclude(status=JobState.CREATED.value, scheduled_at__isnull=True)
            .order_by("-created_at")
        )

        if not unfinished_jobs.exists():
            self.stdout.write(self.style.SUCCESS("✓ No unfinished jobs found!"))
            return

        self.stdout.write(f"Found {unfinished_jobs.count()} unfinished jobs:\n")

        for job in unfinished_jobs:
            status_color = self.style.WARNING
            if job.status == JobState.STARTED.value:
                status_color = self.style.HTTP_INFO
            elif job.status in [JobState.PENDING.value, JobState.CREATED.value]:
                status_color = self.style.NOTICE

            time_info = ""
            if job.started_at:
                elapsed = timezone.now() - job.started_at
                hours = elapsed.total_seconds() / 3600
                time_info = f" (running {hours:.1f}h)"
            elif job.scheduled_at:
                elapsed = timezone.now() - job.scheduled_at
                minutes = elapsed.total_seconds() / 60
                time_info = f" (scheduled {minutes:.1f}m ago)"

            task_status = "✓" if job.task_id else "✗"

            self.stdout.write(
                f"  [{task_status}] Job #{job.pk:4d}: "
                f"{status_color(job.status):15s} "
                f"{job.name[:40]:40s} "
                f"{time_info}"
            )

        self.stdout.write("\n💡 Use --check-job <ID> to check a specific job")
        self.stdout.write("💡 Use --check-all to check all without saving changes")
        self.stdout.write("💡 Use --update-all to check and update all unfinished jobs")

    def show_job_info(self, job_id: int):
        """Show detailed information about a job."""
        job = self.get_job(job_id)

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Job #{job_id} Detailed Information")
        self.stdout.write(f"{'='*60}\n")

        # Basic info
        self.stdout.write(f"Name: {job.name}")
        self.stdout.write(f"Type: {job.job_type_key}")
        self.stdout.write(f"Project: {job.project.name} (#{job.project.pk})")

        # Status info
        self.stdout.write(f"\n--- Status ---")
        status_color = self.style.SUCCESS if job.status in JobState.final_states() else self.style.WARNING
        self.stdout.write(f"Status: {status_color(job.status)}")
        self.stdout.write(f"Task ID: {job.task_id or '(none)'}")

        # Timestamps
        self.stdout.write(f"\n--- Timestamps ---")
        self.stdout.write(f"Created: {job.created_at}")
        self.stdout.write(f"Updated: {job.updated_at}")
        self.stdout.write(f"Scheduled: {job.scheduled_at or '(never)'}")
        self.stdout.write(f"Started: {job.started_at or '(never)'}")
        self.stdout.write(f"Finished: {job.finished_at or '(never)'}")
        self.stdout.write(f"Last Checked: {job.last_checked_at or '(never)'}")

        # Duration
        if job.started_at:
            if job.finished_at:
                duration = job.finished_at - job.started_at
                self.stdout.write(f"Duration: {duration}")
            else:
                elapsed = timezone.now() - job.started_at
                self.stdout.write(f"Running for: {elapsed}")

        # Progress
        self.stdout.write(f"\n--- Progress ---")
        self.stdout.write(f"Overall: {job.progress.summary.progress:.1%}")
        self.stdout.write(f"Stages: {len(job.progress.stages)}")
        for stage in job.progress.stages:
            self.stdout.write(f"  - {stage.name}: {stage.progress:.1%} ({stage.status})")

        # Celery task info
        if job.task_id:
            self.stdout.write(f"\n--- Celery Task ---")
            try:
                task = AsyncResult(job.task_id)
                self.stdout.write(f"Status: {task.status}")
                self.stdout.write(f"Ready: {task.ready()}")
                if task.ready():
                    self.stdout.write(f"Successful: {task.successful()}")
                    if not task.successful():
                        self.stdout.write(f"Error: {task.result}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))

        # Logs
        if job.logs.stderr:
            self.stdout.write(f"\n--- Recent Errors ---")
            for error in job.logs.stderr[:5]:
                self.stdout.write(self.style.ERROR(f"  {error}"))

        if job.logs.stdout:
            self.stdout.write(f"\n--- Recent Logs (last 5) ---")
            for log in job.logs.stdout[:5]:
                self.stdout.write(f"  {log}")

        # Suggestions
        self.stdout.write(f"\n--- Actions ---")
        if job.status in JobState.running_states():
            self.stdout.write(f"  --check-job {job_id}        Check status")
            if job.task_id:
                self.stdout.write(f"  --remove-task {job_id}      Simulate disappeared task")
                self.stdout.write(f"  --corrupt-task {job_id}     Corrupt task_id")
        elif job.status in JobState.failed_states():
            self.stdout.write(f"  Job is in final state ({job.status})")
            self.stdout.write(f"  Use --force to check anyway")

    def create_test_job(self, project_id: int, options: dict):
        """Create and run a long-running test job."""
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project {project_id} does not exist")

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Creating Test Job for Project #{project_id}: {project.name}")
        self.stdout.write(f"{'='*60}\n")

        # Create a job with 5 minutes of delay (300 seconds)
        # This makes it easy to test various scenarios during its runtime
        job = Job.objects.create(
            job_type_key=MLJob.key,
            project=project,
            name=f"Test Job - Created at {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            delay=300,  # 5 minutes
        )

        self.stdout.write(f"Created Job #{job.pk}: {job.name}")
        self.stdout.write(f"Duration: 5 minutes (300 seconds)")
        self.stdout.write(f"Status: {job.status}")

        # Run the job
        run_async = options.get("run_async", False)

        if run_async:
            self.stdout.write("\n--- Running Asynchronously ---")
            job.enqueue()
            self.stdout.write(self.style.SUCCESS(f"✓ Job enqueued with task_id: {job.task_id}"))
            self.stdout.write("\nThe job is now running in the background via Celery.")
        else:
            self.stdout.write("\n--- Running Synchronously ---")
            self.stdout.write(self.style.WARNING("This will block for ~5 minutes. Press Ctrl+C to cancel."))
            self.stdout.write("")

            try:
                job.run()
                self.stdout.write(self.style.SUCCESS(f"\n✓ Job completed successfully!"))
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n\n⚠ Interrupted! Job may still be running."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\n✗ Job failed: {e}"))

        job.refresh_from_db()

        self.stdout.write(f"\n--- Job Details ---")
        self.stdout.write(f"Job ID: {job.pk}")
        self.stdout.write(f"Status: {job.status}")
        self.stdout.write(f"Task ID: {job.task_id or '(none)'}")
        self.stdout.write(f"Progress: {job.progress.summary.progress:.1%}")

        self.stdout.write(f"\n--- Testing Ideas ---")
        self.stdout.write(f"  # While it's running, simulate a disappeared task:")
        self.stdout.write(f"  docker compose run --rm django python manage.py debug_jobs --remove-task {job.pk}")
        self.stdout.write(f"")
        self.stdout.write(f"  # Then check if auto-retry kicks in:")
        self.stdout.write(f"  docker compose run --rm django python manage.py debug_jobs --check-job {job.pk}")
        self.stdout.write(f"")
        self.stdout.write(f"  # Corrupt the task_id:")
        self.stdout.write(f"  docker compose run --rm django python manage.py debug_jobs --corrupt-task {job.pk}")
        self.stdout.write(f"")
        self.stdout.write(f"  # Get detailed info:")
        self.stdout.write(f"  docker compose run --rm django python manage.py debug_jobs --info {job.pk}")
