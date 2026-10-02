"""
Write the occurrences people confirmed or identified in one project to a portable bundle.

The bundle names detections, taxa and users by natural keys only (capture path, timestamp,
station, bounding box, detector; GBIF key or name and rank; email), so it can be replayed
onto a database where every id is different with ``import_validated_occurrences``.
"""

import json
import pathlib

from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Project
from ami.main.models_future.validated_occurrences import build_bundle


class Command(BaseCommand):
    help = "Export a project's confirmed occurrences and identifications as a bundle keyed by natural keys."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID to export from.")
        parser.add_argument("--output", type=pathlib.Path, required=True, help="Path of the JSON bundle to write.")

    def handle(self, *args, **options):
        try:
            project = Project.objects.get(pk=options["project"])
        except Project.DoesNotExist as err:
            raise CommandError(f"Project {options['project']} does not exist") from err

        bundle = build_bundle(project)
        output: pathlib.Path = options["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(bundle.as_dict(), indent=1, ensure_ascii=False))

        confirmed = sum(1 for record in bundle.occurrences if record.confirmation)
        identifications = sum(len(record.identifications) for record in bundle.occurrences)
        detections = sum(len(record.detections) for record in bundle.occurrences)
        self.stdout.write(
            f"Wrote {len(bundle.occurrences)} occurrences ({confirmed} confirmed, {identifications} identifications, "
            f"{detections} detections) from project #{project.pk} to {output}"
        )
