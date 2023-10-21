import csv
import json
import logging
import pathlib
import tempfile
import time
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError  # noqa

from ...models import TaxaList, Taxon, TaxonRank

logger = logging.getLogger(__name__)

# Panama species list
# url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQLlxfuzZHrHEeHFXmhjtngy0JFqhdOju-wJGNOCWSAbtsIpoZ8OoQFvW6IsqUaUA/pub?gid=1847011020&single=true&output=csv" # noqa


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


def parse_author_and_year(name: str) -> tuple[str | None, str | None]:
    author, year = None, None
    name = name.strip().strip("()")
    split_name = name.split(",")
    if len(split_name) == 2:
        author = split_name[0]
        year = split_name[1]
    else:
        author = name
    return author, year


def fix_columns(taxon_data: dict) -> dict:
    # lowercase all columns, strip whitespace, replace spaces with underscores
    fixed_taxon_data = {}
    for key, value in taxon_data.items():
        new_key = key.lower().strip().replace(" ", "_")
        fixed_taxon_data[new_key] = value
        if new_key == "author":
            author, year = parse_author_and_year(value)
            fixed_taxon_data["author"] = author
            fixed_taxon_data["year"] = year

    return fixed_taxon_data


def create_root_taxon() -> Taxon:
    root_taxon_parent, created = Taxon.objects.get_or_create(
        name="Lepidoptera", rank="ORDER", defaults={"ordering": 0}
    )
    if created:
        logger.info(f"Created root taxon {root_taxon_parent}")
    else:
        logger.info(f"Found existing root taxon {root_taxon_parent}")
    return root_taxon_parent


class Command(BaseCommand):
    r"""
    Import taxa from a JSON file. Assign their rank, parent taxa, gbif_taxon_key, and accepted_name.

    This is a very specific command for importing taxa from an exiting format. A more general
    import command with support for all taxon ranks & fields should be written.



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
            taxa = read_json(fname)
        elif format == "csv":
            taxa = read_csv(fname)
        else:
            raise CommandError("Please specify a format for the taxa file (json or csv)")

        # Get taxa list name
        if options["list"]:
            list_name = options["list"]
        else:
            list_name = pathlib.Path(fname).stem

        taxalist, created = TaxaList.objects.get_or_create(name=list_name)
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created taxa list "%s"' % taxalist))

        if options["purge"]:
            self.stdout.write(self.style.WARNING("Purging all taxa from the database in 5 seconds..."))
            time.sleep(5)
            count = TaxaList.taxa.count()
            self.stdout.write(f"Purging {count} tax from list {taxalist}..")
            TaxaList.taxa.all().delete()

        root_taxon_parent = create_root_taxon()

        for taxon in taxa:
            # Add all entries to taxalist
            taxon = fix_columns(taxon)
            created_taxa = self.create_taxon(taxon, root_taxon_parent)
            taxalist.taxa.add(*created_taxa)

    def create_taxon(self, taxon_data: dict, root_taxon_parent: Taxon) -> list[Taxon]:
        print(taxon_data)
        taxa = []
        created_taxa = []
        updated_taxa = []

        rank_choices = [rank for rank in TaxonRank]
        parent_taxon = None
        for rank in rank_choices:
            # Create all parents and parents of parents
            # Assume ranks are in order of rank
            if rank.name.lower() in taxon_data:
                name = taxon_data[rank.name.lower()]
                rank = rank.name.upper()
                taxon, created = Taxon.objects.get_or_create(name=name, rank=rank)
                taxa.append(taxon)
                if created:
                    logger.info(f"Created taxon {taxon}")
                    created_taxa.append(taxon)
                if not taxon.parent or taxon.parent != parent_taxon:
                    parent = parent_taxon or root_taxon_parent
                    logger.info(f"Assigning parent of {taxon} to {parent}")
                    taxon.parent = parent
                    taxon.save()
                    updated_taxa.append(taxon)
                parent_taxon = taxon

        accepted_name = taxon_data.get("synonym_of", None)

        specific_taxon = taxa[-1]

        specific_taxon_columns = ["author", "year", "gbif_taxon_key", "bold_taxon_bin", "inat_taxon_id"]

        for column in specific_taxon_columns:
            if column in taxon_data:
                logger.info(f"Setting {column} of {specific_taxon} to {taxon_data[column]}")
                setattr(specific_taxon, column, taxon_data[column])
        specific_taxon.save()
        updated_taxa.append(specific_taxon)

        if accepted_name:
            accepted_taxon, created = Taxon.objects.get_or_create(
                name=accepted_name,
                rank="SPECIES",
                defaults={"parent": parent_taxon},
            )
            if created:
                logger.info(f"Created accepted taxon {accepted_taxon}")
                created_taxa.append(accepted_taxon)

            if specific_taxon.synonym_of != accepted_taxon:
                logger.info(f"Setting synonym_of of {specific_taxon} to {accepted_taxon}")
                specific_taxon.synonym_of = accepted_taxon
                specific_taxon.save()
                updated_taxa.append(specific_taxon)

        return specific_taxon
