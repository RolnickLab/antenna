import csv
import logging
import tempfile
from typing import Any
from urllib.request import urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
from tqdm import tqdm

from ami.main.models import TaxaList, Taxon

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def read_csv(fname: str) -> list[dict[str, Any]]:
    with open(fname) as f:
        reader = csv.DictReader(f)
        taxa = [row for row in reader]
    return taxa


def fetch_url(url: str) -> str:
    """Download data from URL to a temporary file."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        with urlopen(url) as response:
            tmp_file.write(response.read())
            fname = tmp_file.name
    logger.info(f"Downloaded taxa file to {fname}")
    return fname


def fix_columns(taxon_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize column names by converting to lowercase, stripping whitespace,
    and replacing spaces with underscores.
    """
    keys_to_update = []
    for key in taxon_data.keys():
        new_key = key.lower().strip().replace(" ", "_")
        if new_key != key:
            logger.debug(f"Renaming {key} to {new_key}")
        keys_to_update.append((key, new_key))

    for key, new_key in keys_to_update:
        taxon_data[new_key] = taxon_data.pop(key)

    return taxon_data


def fix_values(taxon_data: dict[str, Any]) -> dict[str, Any]:
    """
    Transform values in the data: convert null values to None and convert known types.
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
    """
    Update existing taxa with new data from a CSV file.

    This command allows updating any column in the CSV file that exists in the Taxon model.
    It identifies taxa by name, gbif_taxon_key, or inat_taxon_id.

    Example usage:
    ```
    python manage.py update_taxa --format csv data/taxa_updates.csv
    python manage.py update_taxa --format csv https://example.com/taxa_updates.csv
    ```

    Example CSV format:
    ```
    name,gbif_taxon_key,cover_image_url,cover_image_credit
    Epimartyria auricrinella,12345,https://example.com/image.jpg,Photographer Name
    Dyseriocrania griseocapitella,12346,https://example.com/image2.jpg,Another Photographer
    ```

    You can include any column that exists in the Taxon model.

    @TODO: Add --project parameter(s) to scope the taxa list to specific projects.
    This would allow multiple projects to have taxa lists with the same name.
    Usage would be: --project project-slug --project another-project-slug
    """

    help = "Update existing taxa with new data from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("taxa", type=str, help="Path or URL to taxa CSV file")
        parser.add_argument(
            "--format", type=str, default="csv", help="Format of taxa file (csv is the only supported format)"
        )
        parser.add_argument(
            "--list",
            type=str,
            help="Name of taxa list to assign updated taxa to. "
            "If not provided, taxa will be updated but not assigned to any list.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Show what would be updated without making changes."
        )

    def handle(self, *args, **options):
        fname: str = options["taxa"]

        if fname and fname.startswith("http"):
            fname = fetch_url(url=fname)

        format_type = options["format"]
        if format_type.lower() != "csv":
            raise CommandError("Only CSV format is supported for updating taxa")

        incoming_taxa = read_csv(fname)

        # Get or create taxa list if specified
        # Uses get_or_create_for_project with project=None to create a global list
        taxalist = None
        if options["list"]:
            list_name = options["list"]
            taxalist, created = TaxaList.objects.get_or_create_for_project(name=list_name, project=None)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created new taxa list '{list_name}'"))
            else:
                self.stdout.write(f"Using existing taxa list '{list_name}' with {taxalist.taxa.count()} taxa")

        # We'll search across all taxa regardless of list assignment
        taxa_queryset = Taxon.objects.all()

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))

        total_found = 0
        total_updated = 0
        not_found = []
        # Track field update statistics
        field_update_stats = {}

        for i, taxon_data in enumerate(tqdm(incoming_taxa)):
            num_keys_with_values = len([key for key, value in taxon_data.items() if value])
            logger.debug(f"Processing row {i} of {len(incoming_taxa)} with {num_keys_with_values} keys")

            # Skip rows with no data
            if num_keys_with_values == 0:
                logger.debug(f"Skipping row {i} with no data")
                continue

            # Normalize column names and values
            taxon_data = fix_columns(taxon_data)
            taxon_data = fix_values(taxon_data)

            # First, determine how to find the taxon
            id_keys = ["id", "name", "gbif_taxon_key", "inat_taxon_id", "bold_taxon_bin", "fieldguide_id"]
            query = Q()
            for key in id_keys:
                if key in taxon_data and taxon_data[key] is not None:
                    query |= Q(**{key: taxon_data[key]})

            if not query:
                self.stdout.write(
                    self.style.WARNING(f"Row {i}: No identifier provided. Need one of: {', '.join(id_keys)}")
                )
                continue

            # Find the taxon
            taxon = taxa_queryset.filter(query).first()

            if not taxon:
                not_found.append(taxon_data)
                continue

            total_found += 1

            # Look for fields to update
            update_fields = []
            for field, value in taxon_data.items():
                # Skip identifier fields that are not None on the existing taxon instance
                if field in id_keys and getattr(taxon, field) is not None:
                    logger.debug(f"Row {i}: Skipping identifier field '{field}' for {taxon}")
                    continue

                # Check if field exists on the model
                if hasattr(taxon, field):
                    current_value = getattr(taxon, field)
                    if current_value != value:
                        if not dry_run:
                            setattr(taxon, field, value)
                        update_fields.append(field)

                        # Update field statistics
                        if field not in field_update_stats:
                            field_update_stats[field] = 0
                        field_update_stats[field] += 1

                        logger.debug(f"Row {i}: Updating {field} of {taxon} from '{current_value}' to '{value}'")
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Row {i}: Field '{field}' does not exist on Taxon model, skipping")
                    )

            if update_fields:
                if not dry_run:
                    taxon.updated_at = timezone.now()
                    taxon.save(update_fields=update_fields + ["updated_at"])
                    # Add to the specified taxa list if provided
                    if taxalist:
                        taxalist.taxa.add(taxon)
                    total_updated += 1
                else:
                    self.stdout.write(f"Would update {taxon}: fields {', '.join(update_fields)}")
                    if taxalist:
                        self.stdout.write(f"  And would add to taxa list '{taxalist.name}'")
            else:
                logger.debug(f"Row {i}: No fields to update for {taxon}")

        # Summary output
        self.stdout.write(self.style.SUCCESS(f"Found {total_found} taxa"))
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Would update {total_updated} taxa"))
            if taxalist:
                self.stdout.write(self.style.SUCCESS(f"Would add updated taxa to list '{taxalist.name}'"))

            # Show field update statistics
            if field_update_stats:
                self.stdout.write(self.style.SUCCESS("Field update statistics (would update):"))
                for field, count in sorted(field_update_stats.items(), key=lambda x: x[1], reverse=True):
                    self.stdout.write(f"  {field}: {count} taxa")
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated {total_updated} taxa"))
            if taxalist:
                self.stdout.write(self.style.SUCCESS(f"Added updated taxa to list '{taxalist.name}'"))

            # Show field update statistics
            if field_update_stats:
                self.stdout.write(self.style.SUCCESS("Field update statistics:"))
                for field, count in sorted(field_update_stats.items(), key=lambda x: x[1], reverse=True):
                    self.stdout.write(f"  {field}: {count} taxa")

        if not_found:
            self.stdout.write(self.style.WARNING(f"Could not find {len(not_found)} taxa"))
            for i, data in enumerate(not_found[:5]):  # Show only first 5
                self.stdout.write(f"  {i+1}. {data}")
            if len(not_found) > 5:
                self.stdout.write(f"  ... and {len(not_found) - 5} more")
