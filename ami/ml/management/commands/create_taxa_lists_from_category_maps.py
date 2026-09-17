from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ami.ml.models import Algorithm


class Command(BaseCommand):
    """
    Create or refresh one global taxa list per classification algorithm, holding every
    taxon in the algorithm's category map. Projects can then filter by the list or copy
    it as the starting point for a curated regional list.
    """

    help = "Create or refresh a global taxa list from the category map of each algorithm"

    def add_arguments(self, parser):
        parser.add_argument(
            "--algorithm",
            action="append",
            dest="keys",
            metavar="KEY",
            help="Only this algorithm key (repeatable). Default: every algorithm with a category map.",
        )
        parser.add_argument(
            "--no-create-taxa",
            action="store_true",
            help="Leave out labels with no matching taxon instead of creating a taxon for them.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change and roll everything back.",
        )

    def handle(self, *args, **options):
        algorithms = Algorithm.objects.exclude(category_map=None).select_related("category_map").order_by("pk")
        if options["keys"]:
            algorithms = algorithms.filter(key__in=options["keys"])
            missing = set(options["keys"]) - set(algorithms.values_list("key", flat=True))
            if missing:
                raise CommandError(f"No algorithm with a category map for key(s): {', '.join(sorted(missing))}")

        with transaction.atomic():
            for algorithm in algorithms:
                if not algorithm.has_valid_category_map():
                    self.stdout.write(f"Skipping {algorithm}: empty category map")
                    continue
                result = algorithm.get_or_create_taxa_list(create_missing_taxa=not options["no_create_taxa"])
                verb = "Created" if result.created_list else "Updated"
                self.stdout.write(
                    f"{verb} taxa list '{result.taxa_list.name}' (#{result.taxa_list.pk}): "
                    f"{result.labels} labels, {result.matched} matched existing taxa, "
                    f"{result.created_taxa} taxa created, {len(result.unresolved)} unresolved"
                )
                for label in result.unresolved:
                    self.stdout.write(f"  unresolved: {label}")

            if options["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run: all changes rolled back"))
