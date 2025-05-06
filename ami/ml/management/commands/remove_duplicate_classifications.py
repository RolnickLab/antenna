from django.core.management.base import BaseCommand
from tqdm import tqdm

from ami.main.models import Classification


class Command(BaseCommand):
    help = "Find and remove duplicate classifications on detections"

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, help="Project ID to process")
        parser.add_argument("--dry-run", action="store_true", help="List duplicates without deleting them")

    def handle(self, *args, **options):
        project_id = options["project"]
        dry_run = options["dry_run"]

        duplicates = Classification.objects.find_duplicates(project_id=project_id)  # type: ignore
        total = duplicates.count()
        self.stdout.write(f"Found {total} duplicate classifications")
        if dry_run:
            with tqdm(total=total, desc="Listing duplicates", unit="classification") as pbar:
                for duplicate in duplicates:
                    self.stdout.write(f"Duplicate classification: {duplicate}")
                    pbar.update(1)

        else:
            with tqdm(total=None, desc="Deleting duplicates") as pbar:
                duplicates.delete()
