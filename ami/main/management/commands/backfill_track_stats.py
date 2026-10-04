"""
Store track statistics on the occurrences of one project.

Tracking and regrouping keep ``Occurrence.track_*`` current from the moment the fields
exist; this fills in the rows from before that, so occurrences can be sorted by motion,
size change and identification agreement. Occurrences with several detections are the
ones worth sorting by, so single-detection ones are skipped unless asked for.

Safe to re-run: every pass recomputes from the current detections. ``updated_at`` is
left alone, so the default list order does not change.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from ami.main.models import Occurrence, Project
from ami.main.models_future.track_stats import REFRESH_BATCH_SIZE, refresh_track_stats_for_ids


class Command(BaseCommand):
    help = "Store track statistics (motion, size ratio, distinct taxa, id agreement) on a project's occurrences."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID to backfill.")
        parser.add_argument(
            "--only-multi-detection",
            action="store_true",
            default=True,
            help="Skip occurrences with a single detection (default).",
        )
        parser.add_argument(
            "--all-occurrences",
            action="store_false",
            dest="only_multi_detection",
            help="Include single-detection occurrences as well.",
        )

    def handle(self, *args, **options):
        project_id: int = options["project"]
        only_multi_detection: bool = options["only_multi_detection"]

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist as err:
            raise CommandError(f"Project {project_id} does not exist") from err

        occurrences = Occurrence.objects.filter(project=project)
        if only_multi_detection:
            occurrences = occurrences.annotate(detection_count=Count("detections")).filter(detection_count__gt=1)

        # Materialize the ids first: the refresh writes to the same rows the filter reads.
        ids = list(occurrences.order_by("pk").values_list("pk", flat=True))
        scope = "multi-detection occurrences" if only_multi_detection else "occurrences"
        self.stdout.write(f"Project #{project.pk} ({project.name}): {len(ids)} {scope} to refresh.")

        refreshed = 0
        for start in range(0, len(ids), REFRESH_BATCH_SIZE):
            refreshed += refresh_track_stats_for_ids(ids[start : start + REFRESH_BATCH_SIZE])
            self.stdout.write(f"  {refreshed}/{len(ids)}")

        self.stdout.write(self.style.SUCCESS(f"Stored track statistics for {refreshed} {scope}."))
