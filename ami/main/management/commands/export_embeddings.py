"""
Write one algorithm's detection feature vectors for a project to a directory.

The vectors go to ``vectors.npy`` and each row's detection is named in ``index.csv`` by
its natural key (capture path, timestamp, station, box, detector), so
``import_embeddings`` can put them back on a database where the ids differ.
"""

import pathlib

from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Project
from ami.main.models_future.embedding_transfer import DEFAULT_VECTOR_KEY, export_embeddings, resolve_algorithm
from ami.ml.models import Algorithm


class Command(BaseCommand):
    help = "Export detection feature vectors from one algorithm as vectors.npy plus an index of detection keys."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID to export from.")
        parser.add_argument(
            "--algorithm", required=True, help="Key, name or ID of the algorithm whose vectors to export."
        )
        parser.add_argument("--output", type=pathlib.Path, required=True, help="Directory to write into.")
        parser.add_argument(
            "--vector-key",
            default=DEFAULT_VECTOR_KEY,
            help=f"Which of the algorithm's vectors to export when it stores several (default {DEFAULT_VECTOR_KEY}).",
        )
        parser.add_argument(
            "--dtype", default="float32", choices=["float16", "float32"], help="Storage precision (default float32)."
        )

    def handle(self, *args, **options):
        try:
            project = Project.objects.get(pk=options["project"])
        except Project.DoesNotExist as err:
            raise CommandError(f"Project {options['project']} does not exist") from err
        try:
            algorithm = resolve_algorithm(options["algorithm"])
        except Algorithm.DoesNotExist as err:
            raise CommandError(str(err)) from err

        try:
            manifest = export_embeddings(
                project, algorithm, options["output"], vector_key=options["vector_key"], dtype=options["dtype"]
            )
        except ValueError as err:
            raise CommandError(str(err)) from err
        self.stdout.write(
            f"Wrote {manifest.count} vectors of {manifest.dimensions} dimensions ({manifest.dtype}) from "
            f"{manifest.source_store} for algorithm {algorithm.key!r} in project #{project.pk} to {options['output']}"
        )
