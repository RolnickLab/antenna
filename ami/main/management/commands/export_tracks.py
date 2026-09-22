"""
Write a project's tracks as CSV, one row per detection, for building and scoring a tracking benchmark.

The columns are the ``tracks_csv`` export format's (``ami/exports/tracks.py``), so a file from
this command and a file from the export API can be compared directly. Read-only.
"""

from django.core.management.base import BaseCommand, CommandError

from ami.exports.tracks import write_tracks_csv
from ami.main.models import Occurrence, Project


class Command(BaseCommand):
    help = "Write a project's tracks (one row per detection) as CSV to a file or stdout."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID to export.")
        parser.add_argument(
            "--event",
            type=int,
            action="append",
            dest="events",
            default=[],
            help="Only occurrences of this session (event) ID. Repeat to export several.",
        )
        parser.add_argument(
            "--verified-only",
            action="store_true",
            help="Only occurrences whose grouping a reviewer has confirmed.",
        )
        parser.add_argument("--output", "-o", default="-", help="File path to write, or - for stdout (default).")

    def handle(self, *args, **options):
        project_id: int = options["project"]
        if not Project.objects.filter(pk=project_id).exists():
            raise CommandError(f"Project {project_id} does not exist")

        occurrences = Occurrence.objects.valid().filter(project_id=project_id)  # type: ignore[union-attr]
        if options["events"]:
            occurrences = occurrences.filter(event_id__in=options["events"])
        if options["verified_only"]:
            occurrences = occurrences.filter(grouping_verified_at__isnull=False)

        output: str = options["output"]
        if output == "-":
            rows = write_tracks_csv(occurrences, self.stdout)
        else:
            with open(output, "w", newline="", encoding="utf-8") as stream:
                rows = write_tracks_csv(occurrences, stream)
        # Keep stdout pure CSV when the file goes there; the summary goes to stderr.
        (self.stderr if output == "-" else self.stdout).write(f"Wrote {rows} detection rows.")
