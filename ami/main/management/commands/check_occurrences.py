import logging

from django.core.management.base import BaseCommand

from ami.main.checks import check_occurrences

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check occurrence data integrity and optionally fix issues"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            default=None,
            help="Scope to a single project ID",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Auto-fix issues (missing determinations, orphaned occurrences)",
        )

    def handle(self, *args, **options):
        project_id = options["project_id"]
        fix = options["fix"]

        scope = f"project {project_id}" if project_id else "all projects"
        self.stdout.write(f"Checking occurrence integrity for {scope}...")

        report = check_occurrences(project_id=project_id, fix=fix)

        # Missing determination
        label = "Missing determination"
        count = len(report.missing_determination)
        if fix and report.fixed_determinations:
            self.stdout.write(f"  {label}: {count} found, {report.fixed_determinations} fixed")
        elif count:
            self.stdout.write(self.style.WARNING(f"  {label}: {count} found"))
        else:
            self.stdout.write(f"  {label}: 0")

        # Orphaned occurrences
        label = "Orphaned occurrences"
        count = len(report.orphaned_occurrences)
        if fix and report.deleted_occurrences:
            self.stdout.write(f"  {label}: {count} found, {report.deleted_occurrences} deleted")
        elif count:
            self.stdout.write(self.style.WARNING(f"  {label}: {count} found"))
        else:
            self.stdout.write(f"  {label}: 0")

        # Orphaned detections
        label = "Orphaned detections"
        count = len(report.orphaned_detections)
        if count:
            self.stdout.write(self.style.WARNING(f"  {label}: {count} found"))
        else:
            self.stdout.write(f"  {label}: 0")

        # Summary
        if report.has_issues and not fix:
            self.stdout.write(self.style.NOTICE("\nRun with --fix to repair fixable issues."))
        elif report.has_issues and fix:
            self.stdout.write(self.style.SUCCESS("\nDone. Applied fixes."))
        else:
            self.stdout.write(self.style.SUCCESS("\nNo issues found."))
