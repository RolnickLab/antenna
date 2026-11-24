import pydantic
from django.core.management.base import BaseCommand, CommandError

from ami.main.models import SourceImageCollection, TaxaList
from ami.ml.models.algorithm import Algorithm
from ami.ml.post_processing.class_masking import DEFAULT_OUT_OF_LIST_WEIGHT, ClassMaskingConfig, ClassMaskingTask


class Command(BaseCommand):
    help = (
        "Run class masking post-processing on a source image collection. "
        "Down-weights or removes the classifier's classes for species not in the given taxa list "
        "and recalculates softmax scores."
    )

    def add_arguments(self, parser):
        parser.add_argument("--collection-id", type=int, required=True, help="SourceImageCollection ID to process")
        parser.add_argument("--taxa-list-id", type=int, required=True, help="TaxaList ID to use as the species mask")
        parser.add_argument(
            "--algorithm-id", type=int, required=True, help="Algorithm ID whose classifications to mask"
        )
        parser.add_argument(
            "--out-of-list-weight",
            type=float,
            default=None,
            help=(
                "Weight for classes whose species is outside the taxa list, at least 0 and below 1. "
                f"0 removes them (a hard mask). Default: {DEFAULT_OUT_OF_LIST_WEIGHT:g}"
            ),
        )
        parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")

    def handle(self, *args, **options):
        collection_id = options["collection_id"]
        taxa_list_id = options["taxa_list_id"]
        algorithm_id = options["algorithm_id"]
        dry_run = options["dry_run"]

        # Validate inputs
        try:
            collection = SourceImageCollection.objects.get(pk=collection_id)
        except SourceImageCollection.DoesNotExist:
            raise CommandError(f"SourceImageCollection {collection_id} does not exist.")

        try:
            taxa_list = TaxaList.objects.get(pk=taxa_list_id)
        except TaxaList.DoesNotExist:
            raise CommandError(f"TaxaList {taxa_list_id} does not exist.")

        try:
            algorithm = Algorithm.objects.get(pk=algorithm_id)
        except Algorithm.DoesNotExist:
            raise CommandError(f"Algorithm {algorithm_id} does not exist.")

        if not algorithm.category_map:
            raise CommandError(f"Algorithm '{algorithm.name}' does not have a category map.")

        # Validate the config here, without building the task: the task's constructor
        # writes an Algorithm row, which a dry run or a refused weight must not do.
        config_kwargs = {
            "source_image_collection_id": collection_id,
            "taxa_list_id": taxa_list_id,
            "algorithm_id": algorithm_id,
        }
        if options["out_of_list_weight"] is not None:
            config_kwargs["out_of_list_weight"] = options["out_of_list_weight"]
        try:
            config = ClassMaskingConfig(**config_kwargs)
        except pydantic.ValidationError as e:
            raise CommandError(f"Invalid class masking config: {e}")

        from ami.main.models import Classification

        # Mirrors ClassMaskingTask._scoped_classifications; do not add .distinct(),
        # see #1376.
        classification_count = Classification.objects.filter(
            detection__source_image__collections=collection,
            terminal=True,
            algorithm=algorithm,
            scores__isnull=False,
            logits__isnull=False,
        ).count()

        taxa_count = taxa_list.taxa.count()

        self.stdout.write(
            f"Collection:     {collection.name} (id={collection.pk})\n"
            f"Taxa list:      {taxa_list.name} (id={taxa_list.pk}, {taxa_count} taxa)\n"
            f"Algorithm:      {algorithm.name} (id={algorithm.pk})\n"
            f"Out-of-list weight: {config.out_of_list_weight:g}\n"
            f"Classifications to process: {classification_count}"
        )

        if classification_count == 0:
            raise CommandError("No terminal classifications with scores found for this collection/algorithm.")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        self.stdout.write("Running class masking...")
        task = ClassMaskingTask(**config_kwargs)
        task.run()
        self.stdout.write(self.style.SUCCESS("Class masking completed."))
