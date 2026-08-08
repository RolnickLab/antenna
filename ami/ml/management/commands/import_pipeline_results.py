"""
Import machine-learning results that were produced outside Antenna into an existing project.

Supported input
---------------
A single JSON file containing one ``PipelineResultsResponse`` (the same schema the processing
services return over the API and over NATS). This is exactly the output of the AMI Data Companion's
``ami export api-occurrences`` command. The results carry detections, classifications, the source
images they came from, and optionally the deployments those images belong to.

The file is fed through ``Pipeline.save_results`` — the same function the live processing path uses —
so an import produces the same detections, classifications, and occurrences as if Antenna had run the
pipeline itself.

Not (yet) supported, and good to know before you reach for this command:

- **Only one file at a time.** The Data Companion splits a large export into several
  ``*_batch_001.json``, ``*_batch_002.json`` … files (and an optional ``*_images`` folder of crops).
  Import them one at a time; there is no directory, glob, or zip-archive input yet.
- **Results only, not a whole project.** The target project must already exist (passed by ``--project``).
  This command does not create the project, and it does not import deployment configuration such as
  latitude/longitude, device, or research site — only the deployment *name* carried in the results is
  used to attach captures. With ``--create-missing-source-images`` (always on here) it will create the
  referenced deployments and source images by name, but not their full configuration.
- **No occurrence/track grouping on import.** Antenna's data model already supports an occurrence
  made up of several detections across frames (a track) via ``Detection.occurrence``, and the
  synthetic generators (``create_demo_project``, ``seed_synthetic_occurrences``) build such tracks.
  Antenna does not compute tracks itself, though, and ``PipelineResultsResponse`` currently has no
  field that says "these detections belong to the same occurrence", so this import gives each
  detection its own single-detection occurrence. Carrying track associations produced upstream (in the
  Data Companion or another service) through the schema and into ``save_results`` is a planned
  enhancement; until then the legacy ``occurrences.json`` importer in the ``exports`` app is the only
  path that preserves multi-detection occurrences.

By default the algorithms referenced by the results must already be registered (through a processing
service's ``/info`` endpoint). Pass ``--create-new-algorithms`` to register them from the results file
instead — the common case when importing into an instance that has never seen that pipeline.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ami.main.models import Project
from ami.ml.models.pipeline import save_results
from ami.ml.schemas import PipelineResultsResponse


class Command(BaseCommand):
    help = (
        "Import one PipelineResultsResponse JSON file (e.g. from the AMI Data Companion's "
        "'export api-occurrences' command) into an existing project. See the module docstring for the "
        "supported input format and current limitations (single file, results-only, no track grouping)."
    )

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str, help="Path to JSON file containing PipelineResultsResponse data")
        parser.add_argument("--project", type=int, required=True, help="Project ID to import the data into")
        parser.add_argument("--dry-run", action="store_true", help="Validate the data without saving to database")
        parser.add_argument(
            "--public-base-url",
            type=str,
            help="Base URL for images if paths are relative (e.g., http://0.0.0.0:7070/)",
        )
        parser.add_argument(
            "--create-new-algorithms",
            action="store_true",
            help=(
                "Register algorithms and category maps from the results file instead of requiring them to be "
                "registered in advance through a processing service's /info endpoint. Use this when importing "
                "results for a pipeline whose algorithms are not already known to this Antenna instance."
            ),
        )

    def handle(self, *args, **options):
        json_file_path = Path(options["json_file"])
        project_id = options["project"]
        dry_run = options.get("dry_run", False)
        public_base_url = options.get("public_base_url")
        create_new_algorithms = options.get("create_new_algorithms", False)

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
            # Call the save_results function with create_missing_source_images=True
            results_json = pipeline_results.json()
            with transaction.atomic():
                result = save_results(
                    results_json=results_json,
                    job_id=None,
                    return_created=True,
                    create_missing_source_images=True,
                    project_id=project_id,
                    public_base_url=public_base_url,
                    create_new_algorithms=create_new_algorithms,
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
                        f"\n  - Deployments used: {len(result.deployments)}"
                        f"\n  - Total processing time: {result.total_time:.2f} seconds"
                    )
                )

                # Re-save all deployments in the results to ensure they are up-to-date
                # Must loop through the source images
                self.stdout.write(self.style.SUCCESS("Updating sessions and stations"))
                deployments = {
                    source_image.deployment for source_image in result.source_images if source_image.deployment
                }
                for deployment in deployments:
                    deployment.save(regroup_async=False)
            else:
                self.stdout.write(self.style.WARNING("Import completed but no result object returned"))

        except Exception as e:
            raise CommandError(f"Error importing pipeline results: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Pipeline results successfully imported into project '{project.name}' (ID: {project_id})"
            )
        )
