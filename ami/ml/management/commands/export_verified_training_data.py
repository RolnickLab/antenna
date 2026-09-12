"""
Export human-verified detections as a training set for a classifier head.

The backbone is frozen, so retraining a head means fitting a small matrix over stored
embeddings. This command gathers the labels people have confirmed in the UI, pairs them
with the embeddings saved by the pipeline, and writes them out.

Usage:
    python manage.py export_verified_training_data --project 3 --algorithm bioclip-2-5-nf-749

Writes two files next to each other:
    <output>.npz   embeddings, label indices, detection ids, split assignment
    <output>.json  label map, counts, and the settings used to produce it

The split is deterministic and grouped by occurrence. See training_data.split_for() for why that
matters.
"""

import json
import pathlib

import numpy as np
from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Project
from ami.ml import training_data
from ami.ml.models import Algorithm
from ami.ml.models.embedding import EMBEDDING_DIMENSIONS


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
            help="Drop species with fewer verified crops than this. A class with one example cannot be evaluated.",
        )

    def handle(self, *args, **options):
        project = Project.objects.filter(pk=options["project"]).first()
        if not project:
            raise CommandError(f"No project with id {options['project']}")

        algorithm = Algorithm.objects.filter(key=options["algorithm"]).first()
        if not algorithm:
            known = list(Algorithm.objects.values_list("key", flat=True)[:20])
            raise CommandError(f"No algorithm with key '{options['algorithm']}'. Known keys: {known}")

        occurrence_ids = list(training_data.verified_occurrence_ids(project))
        self.stdout.write(f"Occurrences with a standing identification: {len(occurrence_ids)}")
        if not occurrence_ids:
            raise CommandError("Nothing has been verified in this project yet, so there is nothing to export.")

        rows = list(
            training_data.verified_training_rows(project, algorithm).values_list(
                "detection_id",
                "detection__occurrence_id",
                "detection__occurrence__determination__name",
                "vector",
            )
        )
        self.stdout.write(f"Verified detections with an embedding from {algorithm.key}: {len(rows)}")

        missing = training_data.count_missing_embeddings(project, algorithm)
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"{missing} verified detection(s) have no embedding from this algorithm and were skipped. "
                    "Re-run the pipeline over them with the store_classification_embeddings flag on."
                )
            )
        if not rows:
            raise CommandError("No verified detection has an embedding yet, so there is nothing to train on.")

        # Drop species too rare to both train and evaluate on.
        counts: dict[str, int] = {}
        for _, _, name, _ in rows:
            counts[name] = counts.get(name, 0) + 1
        min_per_species = options["min_per_species"]
        keep = training_data.species_with_enough_examples(counts, min_per_species)
        dropped = sorted(set(counts) - keep)
        if dropped:
            self.stdout.write(
                f"Dropped {len(dropped)} species with fewer than {min_per_species} verified crops: "
                f"{', '.join(dropped[:8])}{' ...' if len(dropped) > 8 else ''}"
            )
        rows = [r for r in rows if r[2] in keep]

        labels = sorted(keep)
        label_to_index = {name: i for i, name in enumerate(labels)}

        embeddings = np.zeros((len(rows), EMBEDDING_DIMENSIONS), dtype=np.float32)
        y = np.zeros(len(rows), dtype=np.int64)
        detection_ids = np.zeros(len(rows), dtype=np.int64)
        splits = []
        for i, (detection_id, occurrence_id, name, vector) in enumerate(rows):
            embeddings[i] = np.asarray(vector.to_list(), dtype=np.float32)
            y[i] = label_to_index[name]
            detection_ids[i] = detection_id
            splits.append(training_data.split_for(occurrence_id, options["split_salt"], options["test_fraction"]))
        split_array = np.array(splits)

        out = pathlib.Path(options["output"])
        np.savez_compressed(
            out.with_suffix(".npz"),
            embeddings=embeddings,
            labels=y,
            detection_ids=detection_ids,
            split=split_array,
        )

        n_train = int((split_array == "train").sum())
        n_test = int((split_array == "test").sum())
        meta = {
            "project": {"id": project.pk, "name": project.name},
            "algorithm": {"key": algorithm.key, "name": algorithm.name, "version": algorithm.version},
            "dimensions": EMBEDDING_DIMENSIONS,
            "classes": labels,
            "counts": {name: counts[name] for name in labels},
            "rows": len(rows),
            "train": n_train,
            "test": n_test,
            "occurrences": len(occurrence_ids),
            "verified_detections_without_embedding": missing,
            "settings": {
                "test_fraction": options["test_fraction"],
                "split_salt": options["split_salt"],
                "min_per_species": options["min_per_species"],
                "split_grouped_by": "occurrence",
            },
        }
        out.with_suffix(".json").write_text(json.dumps(meta, indent=2))

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(rows)} rows over {len(labels)} species "
                f"(train {n_train} / test {n_test}) to {out.with_suffix('.npz')}"
            )
        )
        # Guard against a silently useless export.
        if n_test == 0:
            self.stdout.write(self.style.WARNING("The test split is empty. Verify more occurrences before training."))
