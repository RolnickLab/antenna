"""
Replay a bundle of confirmed occurrences and identifications onto a project.

By default this is a dry run: it finds each detection again and reports how many matched
exactly, how many only by overlap, and how many are missing, without changing a row. With
``--execute`` it regroups the matched detections with the same operations the review
interface uses, records each confirmation under its original reviewer and time, and
re-creates the identifications. Occurrences with a missing detection are reported as
partial and left unconfirmed. Running it twice changes nothing the second time.
"""

import json
import pathlib

from django.core.management.base import BaseCommand, CommandError

from ami.main.models import Project
from ami.main.models_future.detection_matching import DEFAULT_IOU_THRESHOLD
from ami.main.models_future.validated_occurrences import Bundle, ImportOptions, import_bundle


class Command(BaseCommand):
    help = "Replay confirmed occurrences and identifications from a bundle onto a project (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project ID to import into.")
        parser.add_argument("--input", type=pathlib.Path, required=True, help="Path of the JSON bundle to read.")
        parser.add_argument(
            "--execute",
            action="store_true",
            default=False,
            help="Write the changes. Without this flag the command only reports what it would do.",
        )
        parser.add_argument(
            "--iou-threshold",
            type=float,
            default=DEFAULT_IOU_THRESHOLD,
            help=(
                "Lowest intersection over union accepted when no detection has the exact box "
                f"(default {DEFAULT_IOU_THRESHOLD})."
            ),
        )
        parser.add_argument(
            "--create-missing-detections",
            action="store_true",
            default=False,
            help="Recreate a box whose capture exists but that no detector found, as a reviewer-drawn detection.",
        )
        parser.add_argument(
            "--report", type=pathlib.Path, default=None, help="Write the per-occurrence match report as JSON here."
        )

    def handle(self, *args, **options):
        try:
            project = Project.objects.get(pk=options["project"])
        except Project.DoesNotExist as err:
            raise CommandError(f"Project {options['project']} does not exist") from err
        try:
            bundle = Bundle.from_dict(json.loads(options["input"].read_text()))
        except (OSError, ValueError, KeyError) as err:
            raise CommandError(f"Could not read bundle {options['input']}: {err}") from err

        import_options = ImportOptions(
            execute=options["execute"],
            iou_threshold=options["iou_threshold"],
            create_missing_detections=options["create_missing_detections"],
        )
        report = import_bundle(project, bundle, import_options)
        summary = report.summary()

        mode = "Applied" if import_options.execute else "Dry run"
        self.stdout.write(f"{mode} on project #{project.pk} ({project.name}), bundle from {bundle.project_name!r}:")
        self.stdout.write(f"  occurrences: {summary['occurrences_total']} {dict(summary['occurrences'])}")
        self.stdout.write(f"  detections:  {summary['detections_total']} {dict(summary['detections'])}")
        self.stdout.write(
            f"  confirmed: {summary['confirmed']}  identifications applied: {summary['identifications_applied']}"
            f"  skipped: {summary['identifications_skipped']}  detections created: {summary['detections_created']}"
        )
        if summary["determination_mismatches"]:
            self.stdout.write(f"  determinations differing from the bundle: {summary['determination_mismatches']}")
        if summary["missing_users"]:
            self.stdout.write(self.style.WARNING(f"  users not found: {', '.join(summary['missing_users'])}"))
        if summary["missing_taxa"]:
            names = ", ".join(f"{t['name']} ({t['rank']})" for t in summary["missing_taxa"])
            self.stdout.write(self.style.WARNING(f"  taxa not found: {names}"))
        for outcome in report.outcomes:
            if outcome.outcome == "error":
                self.stdout.write(self.style.ERROR(f"  record {outcome.ref}: {outcome.error}"))

        if options["report"]:
            options["report"].parent.mkdir(parents=True, exist_ok=True)
            options["report"].write_text(json.dumps(report.as_dict(), indent=1, default=str))
            self.stdout.write(f"  report written to {options['report']}")
        if not import_options.execute:
            self.stdout.write("Nothing was changed. Re-run with --execute to apply.")
