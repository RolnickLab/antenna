import logging

from django.core.management.base import BaseCommand

from ami.main.models import Project
from ami.users.models import User
from ami.users.roles import BasicMember, ProjectManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Assign default roles to all project members and owners.
    Also, remove is_staff status from non-superusers.

    Usage:
        python manage.py assign_roles
    """

    help = "Assign roles to all project members and remove staff status from non-superusers."

    def handle(self, *args, **options):
        self.assign_project_roles()
        self.remove_non_superuser_staff()
        self.stdout.write(
            self.style.SUCCESS("Project role assignment and staff status cleanup completed successfully.")
        )

    def assign_project_roles(self):
        """Assign roles to all project members and owners."""
        for project in Project.objects.all():
            # Assign "Basic Member" role to all project members
            for member in project.members.all():
                BasicMember.assign_user(user=member, project=project)
                logger.info(f"Assigned BasicMember role to {member.email} in project {project.name}")

            # Assign "Project Manager" role to project owner
            if project.owner:
                ProjectManager.assign_user(user=project.owner, project=project)
                logger.info(f"Assigned ProjectManager role to {project.owner.email} in project {project.name}")

    def remove_non_superuser_staff(self):
        """Remove is_staff status from all users who are not superusers."""
        users = User.objects.filter(is_staff=True, is_superuser=False)
        count = users.update(is_staff=False)
        logger.info(f"Removed staff status from {count} non-superuser users.")
