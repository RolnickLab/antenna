"""
Delete phantom Occurrences and dangling null-marker Detections left by the Issue #1310
field bug, on a per-project basis.

The bug created two categories of rows that should never have been persisted:
- Occurrence rows with no real detections (their only detections are null-marker
  sentinels, or they have none at all), surfaced as ghost rows in the API.
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
    help = "Delete phantom Occurrences and dangling null-marker Detections (Issue #1310)."

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
        # Phantom = an occurrence with NO real (valid) detection backing it: its only detections
        # are null-marker sentinels, or it has none at all. This is the Issue #1310 debris.
        #
        # Deliberately narrower than Occurrence.valid(): valid() ALSO excludes occurrences whose
        # determination is null, but an occurrence that has a real detection and merely a missing
        # determination is a different (partial-write) shape, not #1310 debris. Deleting it would
        # SET_NULL the real detection's occurrence FK (Detection.occurrence is on_delete=SET_NULL),
        # stranding a classified detection on an image that filter_processed_images then skips
        # forever. Those are left for a separate, targeted repair.
        has_valid_detection = Exists(Detection.objects.valid().filter(occurrence_id=OuterRef("pk")))
        phantom_occs = all_occs.exclude(has_valid_detection)

        has_valid_detection = Detection.objects.valid().filter(source_image_id=OuterRef("source_image_id"))
        dangling_null_markers = (
            Detection.objects.filter(source_image__project=project)
            .null_markers()
            .annotate(_has_valid=Exists(has_valid_detection))
            .filter(_has_valid=False)
        )

        phantom_count = phantom_occs.count()
        null_count = dangling_null_markers.count()

        self.stdout.write(f"Project #{project.pk} ({project.name}):")
        self.stdout.write(f"  Phantom occurrences (no real detection backing them): {phantom_count}")
        self.stdout.write(f"  Dangling null-marker detections on images with no real detections: {null_count}")

        if phantom_count == 0 and null_count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to clean up."))
            return

        if not commit:
            self.stdout.write(self.style.WARNING("Dry run — pass --commit to delete."))
            return

        with transaction.atomic():
            dangling_null_markers.delete()
            phantom_occs.delete()

        # Report the pre-calculated counts of the rows we targeted directly. The tuple from
        # .delete() also counts cascade-deleted related rows (e.g. classifications under a
        # phantom occurrence's detections), which would inflate the numbers and confuse the
        # operator about what the command actually targeted.
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {phantom_count} phantom occurrences and {null_count} dangling null markers.")
        )
