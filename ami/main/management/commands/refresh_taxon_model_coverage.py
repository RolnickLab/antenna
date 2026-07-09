import logging

from django.core.management.base import BaseCommand, CommandError

from ami.main.services.taxon_coverage import refresh_all_algorithm_coverage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Rebuild Taxon.covered_by_algorithms / Taxon.has_model_coverage for every
    algorithm with a category map.

    This is a full repair tool: the persisted model-coverage relationship is
    normally kept fresh automatically (Algorithm.save() refreshes it whenever an
    algorithm's category map changes), so this command is for the initial backfill
    after the fields were added, or to repair drift from a write path that bypassed
    the hook (e.g. a bulk_update on Algorithm.category_map).

    **Usage:**
        python manage.py refresh_taxon_model_coverage
    """

    help = "Rebuild the Taxon <-> Algorithm model-coverage relationship for every algorithm with a category map."

    def handle(self, *args, **options):
        try:
            maps_processed = refresh_all_algorithm_coverage()
        except Exception as e:
            raise CommandError(f"Failed to refresh taxon model coverage: {e}") from e

        self.stdout.write(self.style.SUCCESS(f"Refreshed model coverage from {maps_processed} category map(s)."))
