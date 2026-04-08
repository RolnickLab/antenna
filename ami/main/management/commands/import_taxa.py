import csv
import datetime
import json
import logging
import pathlib
import re
import tempfile
import time
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError  # noqa

# import progress bar
from tqdm import tqdm

from ...models import TaxaList, Taxon, TaxonRank

RANK_CHOICES = [rank for rank in TaxonRank]

logger = logging.getLogger(__name__)
# Set level
logger.setLevel(logging.INFO)

# Panama species list
# url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQLlxfuzZHrHEeHFXmhjtngy0JFqhdOju-wJGNOCWSAbtsIpoZ8OoQFvW6IsqUaUA/pub?gid=1847011020&single=true&output=csv" # noqa

# Panama genera
# https://docs.google.com/spreadsheets/d/e/2PACX-1vQFY_FmkjS1GYpNccRQaRMt4I7yIXmErieu5LMK23HZLsBUbfBXtOr749vMfD9qJfpmTJSnAPrp3hGp/pub?gid=409403959&single=true&output=csv # noqa

# Arthropod upper ranks
# https://docs.google.com/spreadsheets/d/e/2PACX-1vRzHE3kjjIc8iWV1Be4hlTUBU4M1oD7R5h3imEZcsO5C2MWLlk40FolNfkAZiQetyhxm7ya6DDPd9Ye/pub?gid=0&single=true&output=csv # noqa
# docker compose  run --rm django python manage.py import_taxa --format csv https://docs.google.com/spreadsheets/d/e/2PACX-1vRzHE3kjjIc8iWV1Be4hlTUBU4M1oD7R5h3imEZcsO5C2MWLlk40FolNfkAZiQetyhxm7ya6DDPd9Ye/pub\?gid\=0\&single\=true\&output\=csv --list upper-ranks  # noqa


def read_csv(fname: str) -> list[dict]:
    reader = csv.DictReader(open(fname))
    taxa = [row for row in reader]
    return taxa


def read_json(fname: str) -> list[dict]:
    taxa = json.load(open(fname))
    return taxa


def fetch_url(url: str) -> str:
    # Download fname to a temporary file using python standard library

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        with urlopen(url) as response:
            tmp_file.write(response.read())
            fname = tmp_file.name
    logger.info(f"Downloaded taxa file to {fname}")
    return fname


def parse_author_and_year(name: str) -> tuple[str | None, datetime.date | None]:
    author, year = None, None
    name = name.strip().strip("()[]")
    split_name = name.split(",")
    if len(split_name) == 2:
        author = split_name[0]
        year = split_name[1].strip()
        # parse 4 digit year from string using regex
        # and convert date object
        year_match = re.search(r"\d{4}", year)
        if year_match:
            year = year_match.group()
            year = datetime.datetime.strptime(year, "%Y").date()
        else:
            year = None
    else:
        author = name
    return author, year


def fix_generic_names(taxon_data: dict) -> dict:
    # For names that contain "sp", use BOLD BIN as name
    fixed_taxon_data = taxon_data.copy()
    generic_names = ["sp.", "sp", "spp", "spp.", "cf.", "cf", "aff.", "aff"]
    fallback_name_keys = ["bold_taxon_bin", "inat_taxon_id", "gbif_taxon_key"]
    for key, value in taxon_data.items():
        if value and value.lower() in generic_names:
            # set name to first fallback name that exists
            fallback_name = None
            for fallback_name_key in fallback_name_keys:
                fallback_name = taxon_data.get(fallback_name_key, None)
                if fallback_name:
                    logger.info(f"Setting name of {taxon_data} to {fallback_name}")
                    fixed_taxon_data["name"] = fallback_name
                    break
            if not fallback_name:
                raise ValueError(f"Could not find fallback name for generic taxon {taxon_data}")

    return fixed_taxon_data


def fix_columns(taxon_data: dict) -> dict:
    # lowercase all columns, strip whitespace, replace spaces with underscores
    keys_to_update = []
    for key in taxon_data.keys():
        new_key = key.lower().strip().replace(" ", "_")
        if new_key != key:
            logger.debug(f"Renaming {key} to {new_key}")
        keys_to_update.append((key, new_key))

    for key, new_key in keys_to_update:
        taxon_data[new_key] = taxon_data.pop(key)

    if "author" in taxon_data:
        value = taxon_data["author"]
        author, year = parse_author_and_year(value)
        taxon_data["author"] = author
        taxon_data["authorship_date"] = year

    return taxon_data


def fix_values(taxon_data: dict) -> dict:
    """
    If a value in any cell matches a null value, set it to None

    Convert known types (e.g. "sort_phylogeny" to int)

    @TODO Consider switching to pandas at this point?
    """
    null_values = ["z_unplaced", "incertae_sedis", ""]
    known_types = {"sort_phylogeny": int, "gbif_taxon_key": int, "inat_taxon_id": int}

    for key, value in taxon_data.items():
        if str(value).strip() in null_values:
            logger.debug(f"Setting {key} of {taxon_data} to None")
            value = None
            taxon_data[key] = value

        if value and key in known_types:
            logger.debug(f"Converting {key} to {known_types[key]}")
            taxon_data[key] = known_types[key](value)

    return taxon_data


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


class Command(BaseCommand):
    r"""
    Import taxa from a JSON file. Assign their rank, parent taxa, gbif_taxon_key, and accepted_name.

    This is a very specific command for importing taxa from an exiting format. A more general
    import command with support for all taxon ranks & fields should be written.

    @TODO: Add --project parameter(s) to scope the taxa list to specific projects.
    This would allow multiple projects to have taxa lists with the same name.
    Usage would be: --project project-slug --project another-project-slug

    Example taxa.json
    ```
    [
        {
            "species": "Epimartyria auricrinella",
            "genus": "Epimartyria",
            "family": "Micropterigidae",
            "tribe": "Epimartyriini",
            "author": "(Zeller, 1852)",
            "gbif_taxon_key": 12345,
            "bold_taxon_bin": "EPIMAR",
            "inat_taxon_id": null,
            "synonym_of": "Genus species"
        },
        {
            "species": "Dyseriocrania griseocapitella",
            "genus": "Dyseriocrania",
            "family": "Eriocraniidae",
            "gbif_taxon_key": 12346
        }
    ]
    ```

    Example taxa.csv
    ```
    species,genus,family,tribe,author,gbif_taxon_key,bold_taxon_bin,inat_taxon_id,synonym_of
    Epimartyria auricrinella,Epimartyria,Micropterigidae,Epimartyriini,(Zeller, 1852),12345,EPIMAR,,Genus species
    Dyseriocrania griseocapitella,Dyseriocrania,Eriocraniidae,,,(Zeller, 1852),12346,,,
    ```
    """

    help = "Import taxa from a JSON or CSV file. Assign their rank and parent taxon. Create parents if necessary."

    def add_arguments(self, parser):
        parser.add_argument("taxa", type=str, help="Path or URL to taxa JSON or CSV file")
        parser.add_argument("--format", type=str, help="Format of taxa file (json or csv)")
        parser.add_argument("--list", type=str, help="Name of taxa list to add taxa to")
        # Boolean argument to purge all taxa from the database before importing
        parser.add_argument("--purge", action="store_true", help="Purge all taxa from the database before importing.")

    def handle(self, *args, **options):
        fname: str = options["taxa"]

        if fname and fname.startswith("http"):
            fname = fetch_url(url=fname)

        format = options["format"]
        if not format:
            if fname.lower().endswith(".json"):
                format = "json"
            elif fname.lower().endswith(".csv"):
                format = "csv"

        if format == "json":
            incoming_taxa = read_json(fname)
        elif format == "csv":
            incoming_taxa = read_csv(fname)
        else:
            raise CommandError("Please specify a format for the taxa file (json or csv)")

        # Get taxa list name
        if options["list"]:
            list_name = options["list"]
        else:
            list_name = pathlib.Path(fname).stem

        # Uses get_or_create_for_project with project=None to create a global list
        taxalist, created = TaxaList.objects.get_or_create_for_project(name=list_name, project=None)
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created taxa list "%s"' % taxalist))

        if options["purge"]:
            self.stdout.write(self.style.WARNING("Purging all taxa from the database in 5 seconds..."))
            time.sleep(5)
            count = taxalist.taxa.count()
            self.stdout.write(f"Purging {count} tax from list {taxalist}..")
            # show status indicator while deleting taxa with unknown total
            with tqdm():
                taxalist.taxa.all().delete()

        root_taxon_parent = get_or_create_root_taxon()

        total_created_taxa = 0
        total_updated_taxa = 0
        taxa_to_refresh: set[Taxon] = set()

        for i, taxon_data in enumerate(tqdm(incoming_taxa)):
            num_keys_with_values = len([key for key, value in taxon_data.items() if value])
            logger.debug(f"Importing row {i} of {len(incoming_taxa)} with {num_keys_with_values} keys")
            # Skip rows with no data
            if num_keys_with_values == 0:
                logger.debug(f"Skipping row {i} with no data")
                continue
            # Add all entries to taxalist
            taxon_data = fix_columns(taxon_data)
            taxon_data = fix_values(taxon_data)
            logger.debug(f"Parsed taxon data: {taxon_data}")
            if taxon_data:
                created_taxa, updated_taxa, specific_taxon = self.create_taxon(taxon_data, root_taxon_parent)
                taxa_to_refresh.update(created_taxa)
                taxa_to_refresh.update(updated_taxa)
                taxalist.taxa.add(specific_taxon)
                if created_taxa:
                    logger.debug(f"Created {len(created_taxa)} taxa from incoming row {i}")
                    taxalist.taxa.add(*created_taxa)
                    total_created_taxa += len(created_taxa)
                if updated_taxa:
                    logger.debug(f"Updated {len(updated_taxa)} taxa from incoming row {i}")
                    taxalist.taxa.add(*updated_taxa)
                    total_updated_taxa += len(updated_taxa)
            if not taxon_data:
                raise ValueError(f"Could not find any data to import in {taxon_data}")

        logger.info("SUMMARY:")
        logger.info(f"Created {total_created_taxa} total taxa")
        logger.info(f"Updated {total_updated_taxa} total taxa")
        logger.info(f"Total taxa in list {taxalist}: {taxalist.taxa.count()}")

        # Ensure the root taxon still exists and has no parent
        root = Taxon.objects.root()
        if not root:
            root_taxon_parent.parent = None
            root_taxon_parent.save()

        logger.info("Updating cached values for all new or updated taxa")
        for taxon in tqdm(taxa_to_refresh):
            taxon.save(update_calculated_fields=True)

    def create_taxon(self, taxon_data: dict, root_taxon_parent: Taxon) -> tuple[set[Taxon], set[Taxon], Taxon]:
        taxa_in_row = []
        created_taxa = set()
        updated_taxa = set()

        # parent_must_match = ["SPECIES"]#], "SUBSPECIES", "VARIETY", "FORM"]
        global parent_taxon
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
                        logger.info(
                            f"Changing {column} of {specific_taxon} to from {existing_value} to {incoming_value}"
                        )
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

        #

        return created_taxa, updated_taxa, specific_taxon
