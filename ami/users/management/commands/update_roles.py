import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from ami.main.models import Project
from ami.users.models import RoleSchemaVersion
from ami.users.roles import create_roles_for_project

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update roles and permissions for all projects or a specific project"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-id",
            type=int,
            help="Update roles for a specific project by ID",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=True,
            help="Force update even if groups already exist (default: True)",
        )

    def handle(self, *args, **options):
        project_id = options.get("project_id")
        dry_run = options.get("dry_run", False)
        force = options.get("force", True)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))

        # Get projects to update
        if project_id:
            try:
                projects = [Project.objects.get(pk=project_id)]
                self.stdout.write(f"Updating roles for project {project_id}")
            except Project.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Project with ID {project_id} does not exist"))
                return
        else:
            projects = Project.objects.all()
            project_count = projects.count()
            self.stdout.write(f"Updating roles for {project_count} projects")

        success = 0
        failed = 0

        for project in projects:
            try:
                if dry_run:
                    self.stdout.write(f"  Would update roles for project {project.pk} ({project.name})")
                else:
                    with transaction.atomic():
                        create_roles_for_project(project, force_update=force)
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ Updated roles for project {project.pk} ({project.name})")
                    )
                success += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  ✗ Failed to update project {project.pk} ({project.name}): {e}"))
                failed += 1
                logger.exception(f"Error updating roles for project {project.pk}")

        # Summary
        self.stdout.write("\n" + "=" * 50)
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN COMPLETE: Would update {success} projects"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated: {success} projects"))

            if failed > 0:
                self.stdout.write(self.style.ERROR(f"Failed: {failed} projects"))

            # Update schema version if successful and not dry run
            if success > 0 and not project_id:
                RoleSchemaVersion.mark_updated(description="Manual update via management command")
                current_version = RoleSchemaVersion.get_current_version()
                self.stdout.write(f"Schema version updated to: {current_version}")
