import logging
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from tqdm import tqdm

from ami.main.models import Occurrence, update_occurrence_determination

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update cached determination fields for all occurrences"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Number of occurrences to process in each batch",
        )
        parser.add_argument(
            "--project-id",
            type=int,
            default=None,
            help="Limit to a specific project (optional)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of occurrences to process (optional, for testing)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Don't actually update the database",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        project_id = options["project_id"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        # Build the queryset
        qs = Occurrence.objects.all()

        if project_id:
            qs = qs.filter(project_id=project_id)
            self.stdout.write(f"Limiting to occurrences from project {project_id}")

        if limit:
            qs = qs[:limit]
            self.stdout.write(f"Limiting to {limit} occurrences")

        total = qs.count()
        self.stdout.write(f"Processing {total} occurrences")

        if dry_run:
            self.stdout.write("DRY RUN - no changes will be made")

        # Keep track of stats
        updated_count = 0
        field_update_stats = Counter()

        # Process in batches with a progress bar
        with tqdm(total=total, desc="Updating occurrences") as progress_bar:
            # Process occurrences in batches to avoid memory issues
            offset = 0
            while offset < total:
                # Use slice syntax with noqa comment to ignore flake8 warning
                batch = qs[offset : offset + batch_size]  # noqa: E203
                offset += batch_size
                batch_updates = 0

                # Collections for bulk updating
                bulk_updates: dict[str, list[Occurrence]] = {}

                # Use a transaction for each batch
                with transaction.atomic():
                    for occurrence in batch:
                        # Call the update function from models.py
                        updated_occurrence, updated_fields = update_occurrence_determination(
                            occurrence=occurrence, save=False
                        )

                        if updated_fields:
                            batch_updates += 1
                            # Track which fields were updated
                            field_update_stats.update(updated_fields.keys())

                            # Group occurrences by their updated fields for bulk update
                            fields_key = ",".join(sorted(updated_fields.keys()))
                            if fields_key not in bulk_updates:
                                bulk_updates[fields_key] = []
                            bulk_updates[fields_key].append(updated_occurrence)

                    # Perform bulk updates for each group of fields
                    if not dry_run:
                        for fields_key, occurrences in bulk_updates.items():
                            field_names = fields_key.split(",")
                            Occurrence.objects.bulk_update(occurrences, field_names, batch_size=batch_size)
                            self.stdout.write(
                                f"Bulk updated {len(occurrences)} occurrences with fields: {field_names}"
                            )

                # Update counters and progress
                updated_count += batch_updates
                progress_bar.update(len(batch))
                if batch_updates > 0:
                    self.stdout.write(f"Updated {batch_updates} occurrences in this batch")

                if field_update_stats:
                    self.stdout.write("Details:")
                    for field, count in field_update_stats.most_common():
                        self.stdout.write(f"  {field}: {count} occurrences")

        # Report results
        self.stdout.write(self.style.SUCCESS(f"Completed! Updated {updated_count} of {total} occurrences"))

        # Report field update statistics
        self.stdout.write("Summary:")
        for field, count in field_update_stats.most_common():
            self.stdout.write(f"  {field}: {count} occurrences")


# No typer CLI entrypoint - we're using Django's management command system
