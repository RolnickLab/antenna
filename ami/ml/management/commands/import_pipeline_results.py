import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ami.main.models import Project
from ami.ml.models.pipeline import save_results
from ami.ml.schemas import PipelineResultsResponse


class Command(BaseCommand):
    help = "Import pipeline results from a JSON file into the database"

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str, help="Path to JSON file containing PipelineResultsResponse data")
        parser.add_argument("--project", type=int, required=True, help="Project ID to import the data into")
        parser.add_argument("--dry-run", action="store_true", help="Validate the data without saving to database")
        parser.add_argument(
            "--public-base-url",
            type=str,
            help="Base URL for images if paths are relative (e.g., http://0.0.0.0:7070/)",
        )

    def handle(self, *args, **options):
        json_file_path = Path(options["json_file"])
        project_id = options["project"]
        dry_run = options.get("dry_run", False)
        public_base_url = options.get("public_base_url")

        # Validate that the JSON file exists
        if not json_file_path.exists():
            raise CommandError(f"JSON file does not exist: {json_file_path}")

        # Validate that the project exists
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise CommandError(f"Project with ID {project_id} does not exist")

        self.stdout.write(f"Reading JSON file: {json_file_path}")

        # Read and parse the JSON file
        try:
            with open(json_file_path, encoding="utf-8") as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in file {json_file_path}: {e}")
        except Exception as e:
            raise CommandError(f"Error reading file {json_file_path}: {e}")

        # Validate the JSON data against the PipelineResultsResponse schema
        try:
            pipeline_results = PipelineResultsResponse(**json_data)
        except Exception as e:
            raise CommandError(f"Invalid PipelineResultsResponse data: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully validated PipelineResultsResponse with:"
                f"\n  - Pipeline: {pipeline_results.pipeline}"
                f"\n  - Source images: {len(pipeline_results.source_images)}"
                f"\n  - Detections: {len(pipeline_results.detections)}"
                f"\n  - Algorithms: {len(pipeline_results.algorithms)}"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run mode - no data will be saved to database"))
            return

        # Import the data using save_results function
        self.stdout.write(f"Importing data into project: {project} (ID: {project_id})")

        try:
            with transaction.atomic():
                # Call the save_results function with create_missing_source_images=True
                results_json = pipeline_results.json()
                result = save_results(
                    results_json=results_json,
                    job_id=None,
                    return_created=True,
                    create_missing_source_images=True,
                    project_id=project_id,
                    public_base_url=public_base_url,
                )

                if result:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully imported pipeline results:"
                            f"\n  - Pipeline: {result.pipeline}"
                            f"\n  - Source images processed: {len(result.source_images)}"
                            f"\n  - Detections created: {len(result.detections)}"
                            f"\n  - Classifications created: {len(result.classifications)}"
                            f"\n  - Algorithms used: {len(result.algorithms)}"
                            f"\n  - Total processing time: {result.total_time:.2f} seconds"
                        )
                    )
                else:
                    self.stdout.write(self.style.WARNING("Import completed but no result object returned"))

        except Exception as e:
            raise CommandError(f"Error importing pipeline results: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Pipeline results successfully imported into project '{project.name}' (ID: {project_id})"
            )
        )
