"""
Management command to test Pipeline.save_results() with JSON input.

Usage:
    python manage.py test_save_results <pipeline_id> <json_file> <project_id>

Example:
    python manage.py test_save_results 42 results.json 1
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ami.jobs.models import Job, MLJob
from ami.main.models import Project
from ami.ml.models import Pipeline
from ami.ml.schemas import PipelineResultsResponse


class Command(BaseCommand):
    help = "Test Pipeline.save_results() by loading results from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "pipeline_id",
            type=int,
            help="ID of the Pipeline to use for saving results",
        )
        parser.add_argument(
            "json_file",
            type=str,
            help="Path to JSON file containing PipelineResultsResponse data",
        )
        parser.add_argument(
            "project_id",
            type=int,
            help="ID of the Project to associate with the test Job",
        )

    def handle(self, *args, **options):
        pipeline_id = options["pipeline_id"]
        json_file = options["json_file"]
        project_id = options["project_id"]

        # Load and validate the pipeline
        try:
            pipeline = Pipeline.objects.get(pk=pipeline_id)
        except Pipeline.DoesNotExist:
            raise CommandError(f"Pipeline with ID {pipeline_id} does not exist")

        self.stdout.write(f"Using pipeline: {pipeline.name} (ID: {pipeline_id})")

        # Load JSON file
        json_path = Path(json_file)
        if not json_path.exists():
            raise CommandError(f"JSON file not found: {json_file}")

        self.stdout.write(f"Loading results from: {json_file}")
        with json_path.open() as f:
            results_data = json.load(f)

        # Parse and validate using Pydantic
        try:
            results = PipelineResultsResponse(**results_data)
        except Exception as e:
            raise CommandError(f"Failed to parse JSON as PipelineResultsResponse: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Parsed results: {len(results.source_images)} source images, "
                f"{len(results.detections)} detections"
            )
        )

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project with ID {project_id} does not exist")

        # Create a minimal test job
        job = Job.objects.create(
            project=project,
            job_type_key=MLJob.key,
            pipeline_id=pipeline_id,
            name=f"Test save_results ({json_path.name})",
        )
        self.stdout.write(self.style.WARNING(f"Created test job: {job.pk}"))

        # Call save_results
        self.stdout.write("Calling Pipeline.save_results()...")
        try:
            pipeline.save_results(results, job_id=job.pk)
            self.stdout.write(self.style.SUCCESS("✓ save_results() completed successfully"))
        except Exception as e:
            raise CommandError(f"save_results() failed: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Results saved for job {job.pk}. "
                f"Check the database for Detection and Classification records."
            )
        )
