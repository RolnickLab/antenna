import logging

from django.core.management.base import BaseCommand, CommandError  # noqa
from django.db.models import OuterRef, Subquery

from ...models import Detection, SourceImage

logger = logging.getLogger(__name__)


def fix_detection_timestamps(dry_run=True) -> str:
    # Subquery to get the timestamp from the related SourceImage
    source_image_timestamp_subquery = SourceImage.objects.filter(id=OuterRef("source_image_id")).values("timestamp")[
        :1
    ]

    if dry_run:
        # Count all Detection objects where timestamp does not match their SourceImage.timestamp
        count = Detection.objects.exclude(timestamp=Subquery(source_image_timestamp_subquery)).count()
        return f"Would update {count} Detection objects where timestamp does not match their SourceImage.timestamp"

    # Update all Detection objects where timestamp does not match their SourceImage.timestamp
    updated = Detection.objects.exclude(timestamp=Subquery(source_image_timestamp_subquery)).update(
        timestamp=Subquery(source_image_timestamp_subquery)
    )
    return f"Updated {updated} Detection objects where timestamp does not match their SourceImage.timestamp"


class Command(BaseCommand):
    r"""Audit and fix timestamps on Detection objects."""

    help = "Audit and fix timestamps on Detection objects"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Do not make any changes")

    def handle(self, *args, **options):
        msg = fix_detection_timestamps(dry_run=options["dry_run"])
        self.stdout.write(msg)
