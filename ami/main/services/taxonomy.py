"""Shared taxon-creation logic: build a Taxon and its rank hierarchy from a row of
taxonomic data (species/genus/family/...), creating any missing ancestors.

Extracted from ``ami.main.management.commands.import_taxa`` (the ``Command.create_taxon``
method and ``get_or_create_root_taxon``) so the `import_taxa` command and the regional
taxa-list service (`ami.main.services.regional_taxa`) share one implementation instead
of each re-deriving the rank-walk logic. Behaviour is unchanged from the original
command; see `ami/main/management/commands/import_taxa.py::Command` for the CSV/JSON
import entry point that still calls these functions.
"""

import logging

from ..models import Taxon, TaxonRank

RANK_CHOICES = [rank for rank in TaxonRank]

logger = logging.getLogger(__name__)


def get_or_create_root_taxon() -> Taxon:
    """
    Important! This is where the root taxon is configured.
    """
    root_taxon_parent, created = Taxon.objects.get_or_create(
        name="Arthropoda", rank=TaxonRank.PHYLUM.name, defaults={"ordering": 0}
    )
    if created:
        logger.info(f"Created root taxon {root_taxon_parent}")
    else:
        logger.info(f"Found existing root taxon {root_taxon_parent}")
    if root_taxon_parent.parent:
        # If the root taxon has a parent, remove it
        # Otherwise, the root taxon will not be the root and there will be recursion issues
        root_taxon_parent.parent = None
        root_taxon_parent.save()
    return root_taxon_parent


def create_taxon(taxon_data: dict, root_taxon_parent: Taxon) -> tuple[set[Taxon], set[Taxon], Taxon]:
    taxa_in_row = []
    created_taxa = set()
    updated_taxa = set()

    # parent_must_match = ["SPECIES"]#], "SUBSPECIES", "VARIETY", "FORM"]
    parent_taxon = root_taxon_parent

    for i, rank in enumerate(sorted(RANK_CHOICES)):
        logger.debug(f"Checking rank {rank} {i} of {len(RANK_CHOICES)}")
        logger.debug(f"Current parent taxon: {parent_taxon}")
        # Create all parents and parents of parents
        # Assume ranks are in order of rank
        if rank.name.lower() in taxon_data.keys() and taxon_data[rank.name.lower()]:
            name = taxon_data[rank.name.lower()]
            gbif_taxon_key = taxon_data.get("gbif_taxon_key", None)
            rank = rank.name.upper()
            logger.debug(f"Taxon found in incoming row {i}: {rank} {name} (GBIF: {gbif_taxon_key})")

            # Look up existing taxon by name only, since names must be unique.
            # If the taxon already exists, use it and maybe update it
            taxon, created = Taxon.objects.get_or_create(
                name=name,
                defaults=dict(
                    rank=rank,
                    gbif_taxon_key=gbif_taxon_key,
                    parent=parent_taxon,
                ),
            )
            taxa_in_row.append(taxon)

            if created:
                logger.debug(f"Created new taxon #{taxon.id} {taxon} ({taxon.rank})")
                created_taxa.add(taxon)
            else:
                logger.debug(f"Using existing taxon #{taxon.id} {taxon} ({taxon.rank})")

            # Add or update the rank of the taxon based on incoming data
            if not taxon.rank or taxon.rank != rank:
                if not created:
                    logger.warning(f"Rank of existing {taxon} is changing from {taxon.rank} to {rank}")
                taxon.rank = rank
                taxon.save(update_calculated_fields=False)
                if not created:
                    updated_taxa.add(taxon)

            # Add or update the parent of the taxon based on incoming data
            # if the incoming parent is more specific than the existing parent
            # (e.g. if the existing parent is Lepidoptera and the existing parent is a family)
            if not taxon.parent or parent_taxon.get_rank() > taxon.parent.get_rank():
                parent = parent_taxon or root_taxon_parent
                if parent == taxon:
                    logger.debug(f"Parent of {taxon} is itself, changing to (or keeping as) None")
                    parent = None
                if taxon.parent != parent:
                    if not created:
                        logger.warn(f"Changing parent of {taxon} from {taxon.parent} to more specific {parent}")
                    taxon.parent = parent
                    taxon.save(update_calculated_fields=False)
                    if not created:
                        updated_taxa.add(taxon)

            parent_taxon = taxon
            logger.debug(f"Next parent taxon: {parent_taxon.rank} {parent_taxon}")
        else:
            logger.debug(f"Did not find {rank} in incoming row, checking next rank")

    accepted_name = taxon_data.get("synonym_of", None)

    if not taxa_in_row:
        raise ValueError(f"Could not find any ranks in {taxon_data}")

    # Make sure incoming taxa are sorted by rank
    taxa_in_row = sorted(taxa_in_row, key=lambda taxon: taxon.get_rank())

    logger.debug(f"Found {len(taxa_in_row)} taxa in row: {taxa_in_row}")

    specific_taxon = taxa_in_row[-1]
    expected_specific_taxon_ranks = TaxonRank.SPECIES, TaxonRank.GENUS
    if specific_taxon.get_rank() not in expected_specific_taxon_ranks:
        logger.warn(f"Assumming the most specific taxon of this row is: {specific_taxon} {specific_taxon.rank}")

    specific_taxon_columns = [
        "author",
        "authorship_date",
        "gbif_taxon_key",
        "bold_taxon_bin",
        "inat_taxon_id",
        "common_name_en",
        "notes",
        "sort_phylogeny",
        "fieldguide_id",
        "cover_image_url",
        "cover_image_credit",
    ]

    is_new = specific_taxon in created_taxa
    needs_update = False
    for column in specific_taxon_columns:
        if column in taxon_data:
            existing_value = getattr(specific_taxon, column)
            incoming_value = taxon_data[column]
            if existing_value != incoming_value:
                if incoming_value is None:
                    # Don't overwrite existing values with None.
                    # This could potentially be a command line option to allow users to clear values.
                    logger.debug(f"Not changing {column} of {specific_taxon} from {existing_value} to None")
                    continue
                if not is_new:
                    logger.info(f"Changing {column} of {specific_taxon} to from {existing_value} to {incoming_value}")
                setattr(specific_taxon, column, taxon_data[column])
                needs_update = True
    if needs_update:
        specific_taxon.save(update_calculated_fields=False)
        if not is_new:
            # raise ValueError(f"TAXON DATA CHANGED for {specific_taxon}")
            logger.warning(f"TAXON DATA CHANGED for existing {specific_taxon} ({specific_taxon.id})")
            updated_taxa.add(specific_taxon)

    if accepted_name:
        accepted_taxon, created = Taxon.objects.get_or_create(
            name=accepted_name,
            rank=specific_taxon.rank,
            defaults={"parent": parent_taxon},
        )
        if created:
            logger.info(f"Created accepted taxon {accepted_taxon}")
            created_taxa.add(accepted_taxon)

        if specific_taxon.synonym_of != accepted_taxon:
            logger.info(f"Setting synonym_of of {specific_taxon} to {accepted_taxon}")
            specific_taxon.synonym_of = accepted_taxon
            specific_taxon.save()
            updated_taxa.add(specific_taxon)

    return created_taxa, updated_taxa, specific_taxon
