"""Management command to process a single image through a pipeline for testing/debugging."""

import logging
import time

from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Detection, SourceImage
from ami.ml.models import Pipeline
from ami.ml.orchestration.processing import process_single_source_image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Submit a job to process a single image through a pipeline (for testing/debugging)"

    def add_arguments(self, parser):
        parser.add_argument("image_id", type=int, help="SourceImage ID to process")
        parser.add_argument(
            "--pipeline",
            type=int,
            required=True,
            help="Pipeline ID to use for processing",
        )
        parser.add_argument(
            "--wait",
            action="store_true",
            help="Wait for the job to complete and show results",
        )

    def handle(self, *args, **options):
        image_id = options["image_id"]
        pipeline_id = options["pipeline"]
        wait = options["wait"]
        poll_interval = 2.0  # seconds
        # Validate image exists
        image: SourceImage
        try:
            image = SourceImage.objects.select_related("deployment__project").get(pk=image_id)
            if not image.deployment or not image.deployment.project:
                raise CommandError(
                    f"SourceImage with id {image_id} is not attached to a deployment/project, cannot submit job"
                )
            self.stdout.write(self.style.SUCCESS(f"✓ Found image: {image.path}"))
            self.stdout.write(f"  Project: {image.deployment.project.name}")
            self.stdout.write(f"  Deployment: {image.deployment.name}")
        except SourceImage.DoesNotExist:
            raise CommandError(f"SourceImage with id {image_id} does not exist")

        # Validate pipeline exists
        try:
            pipeline = Pipeline.objects.get(pk=pipeline_id)
            self.stdout.write(self.style.SUCCESS(f"✓ Using pipeline: {pipeline.name} (v{pipeline.version})"))
        except Pipeline.DoesNotExist:
            raise CommandError(f"Pipeline with id {pipeline_id} does not exist")

        # Submit the job
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Submitting job..."))

        try:
            job = process_single_source_image(
                source_image=image,
                pipeline=pipeline,
                run_async=not wait,
            )
        except Exception as e:
            raise CommandError(f"Failed to submit job: {str(e)}")

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Job {job.pk} created and enqueued\n"
                f"  Task ID: {job.task_id}\n"
                f"  Status: {job.status}\n"
                f"  Name: {job.name}"
            )
        )

        if not wait:
            self.stdout.write("")
            self.stdout.write("To check job status, run:")
            self.stdout.write(f"  Job.objects.get(pk={job.pk}).status")
            return

        # Wait for job completion
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("Waiting for job to complete..."))
        self.stdout.write("(Press Ctrl+C to stop waiting)\n")

        try:
            start_time = time.time()
            last_status = None
            last_progress = None

            while True:
                job.refresh_from_db()
                if job.progress and job.progress.summary and job.progress.summary.progress is not None:
                    progress = job.progress.summary.progress * 100
                else:
                    progress = 0.0
                status = job.status

                # Only update display if something changed
                if status != last_status or abs(progress - (last_progress or 0)) > 0.1:
                    elapsed = time.time() - start_time
                    self.stdout.write(
                        f"  Status: {status:15s} | Progress: {progress:5.1f}% | Elapsed: {elapsed:6.1f}s",
                        ending="\r",
                    )
                    last_status = status
                    last_progress = progress

                # Check if job is done
                if job.status in ["SUCCESS", "FAILURE", "REVOKED", "REJECTED"]:
                    self.stdout.write("")  # New line after progress updates
                    break

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("\n⚠ Stopped waiting (job is still running)"))
            self.stdout.write(f"  Job ID: {job.pk}")
            return

        # Show results
        self.stdout.write("")
        elapsed_total = time.time() - start_time

        if job.status == "SUCCESS":
            self.stdout.write(self.style.SUCCESS(f"✓ Job completed successfully in {elapsed_total:.1f}s"))

            # Show results summary
            detection_count = Detection.objects.filter(source_image_id=image_id).count()
            self.stdout.write("\nResults:")
            self.stdout.write(f"  Detections created: {detection_count}")

            # Show classifications if any
            if detection_count > 0:
                from ami.main.models import Classification

                classification_count = Classification.objects.filter(detection__source_image_id=image_id).count()
                self.stdout.write(f"  Classifications created: {classification_count}")

        elif job.status == "FAILURE":
            self.stdout.write(self.style.ERROR(f"✗ Job failed after {elapsed_total:.1f}s"))
            self.stdout.write("\nCheck job logs for details:")
            self.stdout.write(f"  Job.objects.get(pk={job.pk}).logs")
        else:
            self.stdout.write(self.style.WARNING(f"⚠ Job ended with status: {job.status}"))

        self.stdout.write(f"\nJob ID: {job.pk}")
