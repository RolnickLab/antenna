import logging

from django.core.management.base import BaseCommand
from guardian.shortcuts import get_user_perms, remove_perm

from ami.main.models import Project
from ami.users.models import User
from ami.users.roles import BasicMember, ProjectManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    First, reset permissions for all non-super users.
    Then, remove is_staff status from non-superusers.
    Finally, Assign default roles to all project members and owners.


    Usage:
        python manage.py assign_roles
    """

    help = "Assign roles to all project members and remove staff status from non-superusers."

    def handle(self, *args, **options):
        self.remove_non_superuser_permissions()
        self.remove_non_superuser_staff()
        self.assign_project_roles()

        self.stdout.write(
            self.style.SUCCESS("Project role assignment and staff status cleanup completed successfully.")
        )

    def remove_non_superuser_permissions(self):
        """Remove all permissions and group memberships from non-superusers."""
        users = User.objects.filter(is_superuser=False)
        for user in users:
            for project in Project.objects.all():
                # Remove all object-level permissions
                for perm in get_user_perms(user, project):
                    remove_perm(perm, user, project)

                # Remove user from all groups
                user.groups.clear()
                logger.info(f"Removed all permissions and groups for {user.email} on {project.name}")

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
