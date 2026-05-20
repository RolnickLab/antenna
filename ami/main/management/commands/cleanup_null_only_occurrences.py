"""
Delete phantom Occurrences and orphan null-marker Detections left by the Issue #1310
field bug, on a per-project basis.

The bug created two categories of rows that should never have been persisted:
- Occurrence rows with no real detections (or with determination=NULL), surfaced as
  ghost rows in the API.
- Detection rows that mark a SourceImage as "processed" while no real detections
  exist for it — these prevent filter_processed_images from re-yielding the image
  on the next ML run.

After cleanup, the source images become eligible for re-processing.

Dry-run by default. Pass --commit to delete.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef

from ami.main.models import Detection, Occurrence, Project


class Command(BaseCommand):
    help = "Delete phantom Occurrences and orphan null-marker Detections (Issue #1310)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=int,
            required=True,
            help="Project ID to clean up.",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually delete. Defaults to dry-run.",
        )

    def handle(self, *args, **options):
        project_id: int = options["project"]
        commit: bool = options["commit"]

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist as err:
            raise CommandError(f"Project {project_id} does not exist") from err

        all_occs = Occurrence.objects.filter(project=project)
        valid_occs = all_occs.valid()
        phantom_occs = all_occs.exclude(pk__in=valid_occs.values("pk"))

        has_valid_detection = Detection.objects.valid().filter(source_image_id=OuterRef("source_image_id"))
        orphan_null_markers = (
            Detection.objects.filter(source_image__project=project)
            .null_markers()
            .annotate(_has_valid=Exists(has_valid_detection))
            .filter(_has_valid=False)
        )

        phantom_count = phantom_occs.count()
        null_count = orphan_null_markers.count()

        self.stdout.write(f"Project #{project.pk} ({project.name}):")
        self.stdout.write(f"  Phantom occurrences (no valid detection or null determination): {phantom_count}")
        self.stdout.write(f"  Orphan null-marker detections on images with no real detections: {null_count}")

        if phantom_count == 0 and null_count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to clean up."))
            return

        if not commit:
            self.stdout.write(self.style.WARNING("Dry run — pass --commit to delete."))
            return

        with transaction.atomic():
            null_deleted, _ = orphan_null_markers.delete()
            phantom_deleted, _ = phantom_occs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {phantom_deleted} phantom occurrences and {null_deleted} orphan null markers."
            )
        )
