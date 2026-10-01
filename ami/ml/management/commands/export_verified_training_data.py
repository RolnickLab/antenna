"""
Write a classifier-head training set to a local file, for inspection.

The same set a training job would send to a processing service, saved somewhere you can
open it. It builds the set through ami.ml.training_dataset so the two cannot drift apart:
a file exported here holds exactly what a retrain would have used.

Usage:
    python manage.py export_verified_training_data --project 3 --algorithm bioclip-2-5-nf-749
"""

import json
import pathlib

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Project, TaxaList
from ami.ml import training_data, training_dataset
from ami.ml.models import Algorithm


class Command(BaseCommand):
    help = "Export human-verified detections and their embeddings as a classifier training set"

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID to export from")
        parser.add_argument(
            "--algorithm",
            type=str,
            required=True,
            help=(
                "Key of the algorithm whose embeddings to use. Vectors from different "
                "algorithms are in different spaces and must never be mixed."
            ),
        )
        parser.add_argument("--output", type=str, default="verified_training_data", help="Output path, without suffix")
        parser.add_argument(
            "--taxa-list",
            type=int,
            default=None,
            help="Taxa list to use as the species list. Defaults to the project's own default.",
        )
        parser.add_argument(
            "--test-fraction",
            type=float,
            default=training_data.DEFAULT_TEST_FRACTION,
            help="Share of occurrences held out for evaluation",
        )
        parser.add_argument(
            "--split-salt",
            type=str,
            default=training_data.DEFAULT_SPLIT_SALT,
            help="Changing this reshuffles the split. Keep it fixed to keep an eval set comparable.",
        )
        parser.add_argument(
            "--min-per-species",
            type=int,
            default=2,
            help="Drop species with fewer verified crops than this. Ignored when a taxa list sets the species.",
        )

    def handle(self, *args, **options):
        project = Project.objects.filter(pk=options["project"]).first()
        if not project:
            raise CommandError(f"No project with id {options['project']}")

        algorithm = Algorithm.objects.filter(key=options["algorithm"]).first()
        if not algorithm:
            known = list(Algorithm.objects.values_list("key", flat=True)[:20])
            raise CommandError(f"No algorithm with key '{options['algorithm']}'. Known keys: {known}")

        taxa_list = None
        if options["taxa_list"]:
            taxa_list = TaxaList.objects.filter(pk=options["taxa_list"]).first()
            if not taxa_list:
                raise CommandError(f"No taxa list with id {options['taxa_list']}")

        try:
            result = training_dataset.build_training_dataset(
                project=project,
                algorithm=algorithm,
                min_per_species=options["min_per_species"],
                split_salt=options["split_salt"],
                test_fraction=options["test_fraction"],
                taxa_list=taxa_list,
            )
        except training_dataset.NotEnoughVerifiedData as e:
            raise CommandError(str(e))

        meta = result["metadata"]
        out = pathlib.Path(options["output"])
        with default_storage.open(result["path"], "rb") as stored:
            out.with_suffix(".npz").write_bytes(stored.read())
        out.with_suffix(".json").write_text(json.dumps(meta, indent=2))

        if meta["taxa_list"]:
            self.stdout.write(f"Species list from taxa list '{meta['taxa_list']['name']}'")
        if meta["classes_without_verified_data"]:
            self.stdout.write(
                f"{len(meta['classes_without_verified_data'])} species in the list have no verified crops yet"
            )
        if meta["dropped_species"]:
            self.stdout.write(
                self.style.WARNING(f"{len(meta['dropped_species'])} verified species were left out of the set")
            )
        if meta["verified_detections_without_embedding"]:
            self.stdout.write(
                self.style.WARNING(
                    f"{meta['verified_detections_without_embedding']} verified detection(s) have no embedding "
                    "from this algorithm. Run a generate_embeddings job to include them."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {meta['rows']} rows over {len(meta['classes'])} species "
                f"(train {meta['train']} / test {meta['test']}) to {out.with_suffix('.npz')}"
            )
        )
