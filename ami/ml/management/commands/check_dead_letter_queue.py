"""
Management command to check dead letter queue messages for a job.

Usage:
    python manage.py check_dead_letter_queue <job_id>

Example:
    python manage.py check_dead_letter_queue 123
"""

import asyncio

from django.core.management.base import BaseCommand, CommandError

from ami.ml.orchestration.nats_queue import TaskQueueManager


class Command(BaseCommand):
    help = "Check dead letter queue messages for a job ID"

    def add_arguments(self, parser):
        parser.add_argument(
            "job_id",
            type=int,
            help="Job ID to check for dead letter queue messages",
        )

    def handle(self, *args, **options):
        job_id = options["job_id"]

        try:
            dead_letter_ids = asyncio.run(self._check_dead_letter_queue(job_id))

            if dead_letter_ids:
                self.stdout.write(
                    self.style.WARNING(f"Found {len(dead_letter_ids)} dead letter task(s) for job {job_id}:")
                )
                for image_id in dead_letter_ids:
                    self.stdout.write(f"  - Image ID: {image_id}")
            else:
                self.stdout.write(self.style.SUCCESS(f"No dead letter tasks found for job {job_id}"))

        except Exception as e:
            raise CommandError(f"Failed to check dead letter queue: {e}")

    async def _check_dead_letter_queue(self, job_id: int) -> list[str]:
        """Check for dead letter queue messages using TaskQueueManager."""
        async with TaskQueueManager() as manager:
            return await manager.get_dead_letter_task_ids(job_id)
