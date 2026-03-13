from django.core.management.base import BaseCommand, CommandError

from ami.main.models import SourceImageCollection, TaxaList
from ami.ml.models.algorithm import Algorithm
from ami.ml.post_processing.class_masking import ClassMaskingTask


class Command(BaseCommand):
    help = (
        "Run class masking post-processing on a source image collection. "
        "Masks classifier logits for species not in the given taxa list and recalculates softmax scores."
    )

    def add_arguments(self, parser):
        parser.add_argument("--collection-id", type=int, required=True, help="SourceImageCollection ID to process")
        parser.add_argument("--taxa-list-id", type=int, required=True, help="TaxaList ID to use as the species mask")
        parser.add_argument(
            "--algorithm-id", type=int, required=True, help="Algorithm ID whose classifications to mask"
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

        from ami.main.models import Classification

        classification_count = (
            Classification.objects.filter(
                detection__source_image__collections=collection,
                terminal=True,
                algorithm=algorithm,
                scores__isnull=False,
            )
            .distinct()
            .count()
        )

        taxa_count = taxa_list.taxa.count()

        self.stdout.write(
            f"Collection:     {collection.name} (id={collection.pk})\n"
            f"Taxa list:      {taxa_list.name} (id={taxa_list.pk}, {taxa_count} taxa)\n"
            f"Algorithm:      {algorithm.name} (id={algorithm.pk})\n"
            f"Classifications to process: {classification_count}"
        )

        if classification_count == 0:
            raise CommandError("No terminal classifications with scores found for this collection/algorithm.")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        self.stdout.write("Running class masking...")
        task = ClassMaskingTask(
            collection_id=collection_id,
            taxa_list_id=taxa_list_id,
            algorithm_id=algorithm_id,
        )
        task.run()
        self.stdout.write(self.style.SUCCESS("Class masking completed."))
