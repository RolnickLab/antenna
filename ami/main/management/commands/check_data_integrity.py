import logging

from django.core.management.base import BaseCommand

from ami.main.integrity import reconcile_missing_determinations

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Find and fix occurrences missing determinations."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report issues without fixing them")
        parser.add_argument("--project", type=int, help="Limit to a specific project ID")
        parser.add_argument("--job", type=int, help="Limit to occurrences related to a specific job ID")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("DRY RUN — no changes will be made\n")

        result = reconcile_missing_determinations(
            project_id=options.get("project"),
            job_id=options.get("job"),
            dry_run=dry_run,
        )

        self.stdout.write(f"Checked: {result.checked}")
        if result.fixed:
            self.stdout.write(self.style.SUCCESS(f"Fixed: {result.fixed}"))
        if result.unfixable:
            self.stdout.write(self.style.WARNING(f"Unfixable: {result.unfixable}"))
        if result.checked == 0:
            self.stdout.write(self.style.SUCCESS("No issues found."))
