"""Management command for end-to-end testing of ML jobs."""

import time

from django.core.management.base import BaseCommand, CommandError

from ami.jobs.models import Job, JobDispatchMode, JobState
from ami.main.models import SourceImageCollection
from ami.ml.models import Pipeline


class Command(BaseCommand):
    help = "Run end-to-end test of ML job processing"

    def add_arguments(self, parser):
        parser.add_argument("collection_name", type=str, help="SourceImageCollection name")
        parser.add_argument("pipeline_slug", type=str, help="Pipeline slug")
        parser.add_argument(
            "--dispatch-mode",
            type=str,
            required=True,
            choices=[mode.value for mode in JobDispatchMode],
            help="Job dispatch mode",
        )

    def handle(self, *args, **options):
        collection_name = options["collection_name"]
        pipeline_slug = options["pipeline_slug"]
        dispatch_mode = options["dispatch_mode"]

        # Find collection
        try:
            collection = SourceImageCollection.objects.get(name=collection_name)
            self.stdout.write(self.style.SUCCESS(f"✓ Found collection: {collection.name}"))
            self.stdout.write(f"  Project: {collection.project.name}")
        except SourceImageCollection.DoesNotExist:
            raise CommandError(f"SourceImageCollection '{collection_name}' not found")

        # Find pipeline
        try:
            pipeline = Pipeline.objects.get(slug=pipeline_slug)
            self.stdout.write(self.style.SUCCESS(f"✓ Found pipeline: {pipeline.name} (v{pipeline.version})"))
        except Pipeline.DoesNotExist:
            raise CommandError(f"Pipeline '{pipeline_slug}' not found")

        # Create job
        job = Job.objects.create(
            name=f"E2E Test: {collection.name} -> {pipeline.name} ({dispatch_mode})",
            project=collection.project,
            source_image_collection=collection,
            pipeline=pipeline,
            job_type_key="ml",
            dispatch_mode=dispatch_mode,
        )

        self.stdout.write(f"\n✓ Created job {job.pk}")
        self.stdout.write(f"  Dispatch mode: {dispatch_mode}")

        # Start job
        start_time = time.time()
        job.enqueue()
        self.stdout.write(f"\n🚀 Job started at {time.strftime('%H:%M:%S')}")
        self.stdout.write("(Press Ctrl+C to stop monitoring)\n")

        try:
            self._monitor_job(job, start_time)
        except KeyboardInterrupt:
            self.stdout.write("\n\n⚠ Stopped monitoring (job continues running)")
            self.stdout.write(f"  Job ID: {job.pk}")

    def _monitor_job(self, job, start_time):
        last_progress = {}

        while True:
            elapsed = time.time() - start_time
            job.refresh_from_db()

            # Check if finished
            if job.status in JobState.final_states():
                self._show_final_results(job, start_time)
                break

            # Show progress
            self._show_progress(job, elapsed, last_progress)
            time.sleep(2.0)

    def _show_progress(self, job, elapsed, last_progress):
        progress_parts = [f"⏱ {elapsed:6.1f}s | Status: {job.status}"]

        if job.progress and job.progress.stages:
            for stage in job.progress.stages:
                progress_pct = stage.progress * 100
                key = stage.key
                if key not in last_progress or abs(last_progress[key] - progress_pct) > 0.1:
                    last_progress[key] = progress_pct

                status_icon = "✓" if stage.status == JobState.SUCCESS else "⏳" if stage.progress > 0 else "⏸"
                progress_parts.append(f"{status_icon} {stage.name}: {progress_pct:5.1f}%")

        # Single line output with carriage return
        progress_line = " | ".join(progress_parts)
        self.stdout.write(f"\r{progress_line:<100}", ending="")

    def _show_final_results(self, job, start_time):
        total_time = time.time() - start_time

        self.stdout.write(f"\n\n{'='*50}")

        if job.status == JobState.SUCCESS:
            self.stdout.write(self.style.SUCCESS(f"✅ Job completed successfully"))
        elif job.status == JobState.FAILURE:
            self.stdout.write(self.style.ERROR(f"❌ Job failed"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠ Job ended with status: {job.status}"))

        self.stdout.write(f"\n⏱ Total runtime: {total_time:.2f} seconds")

        # Show final stage stats
        if job.progress and job.progress.stages:
            self.stdout.write("\n📊 Final Results:")
            for stage in job.progress.stages:
                self.stdout.write(f"  {stage.name}: {stage.progress*100:.1f}% ({stage.status})")
                for param in stage.params:
                    if param.value:
                        self.stdout.write(f"    {param.name}: {param.value}")

        self.stdout.write(f"\n🔗 Job ID: {job.pk}")
