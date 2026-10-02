"""
Put detection feature vectors from an ``export_embeddings`` directory onto a project.

Each row's detection is found again by its natural key (capture path and box, with an
overlap fallback) and the vector is stored under the same algorithm. By default this is a
dry run that reports how many detections were found; ``--execute`` writes the rows. A
detection that already has a vector from that algorithm is skipped unless ``--replace``.
"""

import pathlib

from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Project
from ami.main.models_future.detection_matching import DEFAULT_IOU_THRESHOLD
from ami.main.models_future.embedding_transfer import import_embeddings, resolve_algorithm
from ami.ml.models import Algorithm


class Command(BaseCommand):
    help = "Import detection feature vectors from an export directory onto a project (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID to import into.")
        parser.add_argument(
            "--input", type=pathlib.Path, required=True, help="Directory written by export_embeddings."
        )
        parser.add_argument("--execute", action="store_true", default=False, help="Write the rows.")
        parser.add_argument(
            "--algorithm",
            default=None,
            help="Key, name or ID of the algorithm to store the vectors under (default: the one in the manifest).",
        )
        parser.add_argument("--iou-threshold", type=float, default=DEFAULT_IOU_THRESHOLD)
        parser.add_argument(
            "--replace", action="store_true", default=False, help="Overwrite vectors the detections already have."
        )

    def handle(self, *args, **options):
        try:
            project = Project.objects.get(pk=options["project"])
        except Project.DoesNotExist as err:
            raise CommandError(f"Project {options['project']} does not exist") from err
        algorithm = None
        if options["algorithm"]:
            try:
                algorithm = resolve_algorithm(options["algorithm"])
            except Algorithm.DoesNotExist as err:
                raise CommandError(str(err)) from err

        try:
            report = import_embeddings(
                project,
                options["input"],
                execute=options["execute"],
                iou_threshold=options["iou_threshold"],
                replace=options["replace"],
                algorithm=algorithm,
            )
        except (OSError, ValueError, RuntimeError, Algorithm.DoesNotExist) as err:
            raise CommandError(str(err)) from err

        summary = report.summary()
        mode = "Applied" if options["execute"] else "Dry run"
        self.stdout.write(
            f"{mode} on project #{project.pk}: {summary['vectors_total']} vectors, detections {summary['detections']}"
        )
        if options["execute"]:
            self.stdout.write(
                f"  written: {summary['written']}  skipped (already stored): {summary['skipped_existing']}"
                f"  replaced: {summary['replaced']}"
            )
        else:
            self.stdout.write("Nothing was changed. Re-run with --execute to write the vectors.")
