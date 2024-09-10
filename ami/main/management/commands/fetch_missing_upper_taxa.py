import logging

from django.core.management.base import BaseCommand
from tqdm import tqdm

from ami.main.models import Taxon, TaxonRank
from ami.utils.taxonomy.fetch_taxon_data import fetch_col_data_batch

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch and update missing upper taxa for species and genera"

    def handle(self, *args, **options):
        logger.info("Starting to fetch and update missing upper taxa...")

        # dry_run = options.get("dry_run", True)

        # Update the parents_json of all taxa in the database
        logger.info("Updating parents_json for all taxa...")
        Taxon.objects.update_all_parents()

        desired_taxon_ranks = [
            TaxonRank.ORDER,
            TaxonRank.SUPERFAMILY,
            TaxonRank.FAMILY,
            TaxonRank.SUBFAMILY,
            TaxonRank.TRIBE,
            TaxonRank.SUBTRIBE,
            TaxonRank.GENUS,
            TaxonRank.SUBGENUS,
        ]

        # Start with the highest rank and work our way down, making sure that all upper taxa have a parent
        for taxon_rank in tqdm(desired_taxon_ranks, desc="Processing ranks"):
            logger.info(f"Processing rank: {taxon_rank}")

            # Get all taxa that are missing the current rank
            taxa = Taxon.objects.filter(rank=taxon_rank, parent__isnull=True).order_by("id")

            # Process each taxon
            results = fetch_col_data_batch([(taxon_rank.value.lower(), taxon.name) for taxon in taxa])
            print(results)
            # import pdb
            # pdb.set_trace()
            for taxon in tqdm(taxa, desc="Processing taxa"):
                pass

    def process_parent_taxon(self, taxon):
        logger.info(f"Processing taxon: {taxon}")
        fetch_col_data_batch([(taxon.rank, taxon.name)])
        # taxon.save()
