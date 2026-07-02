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

from ...models import TaxaList, Taxon
from ...services.taxonomy import create_taxon, get_or_create_root_taxon

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
                created_taxa, updated_taxa, specific_taxon = create_taxon(taxon_data, root_taxon_parent)
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
