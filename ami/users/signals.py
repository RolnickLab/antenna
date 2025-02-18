from django.db.models.signals import post_migrate
from django.dispatch import receiver

from ami.main.models import Project
from ami.users.roles import BasicMember, ProjectManager, create_roles_for_project


@receiver(post_migrate)
def create_and_assign_roles(sender, **kwargs):
    """Creates predefined roles with specific permissions when the app starts and auto assign them."""

    # Get all Role subclasses dynamically
    for project in Project.objects.all():
        create_roles_for_project(project)
        # Assign "Basic Member" role to all project members
        for member in project.members.all():
            BasicMember.assign_user(user=member, project=project)
        # Assign "Project Manager" role to all project members
        if project.owner:
            ProjectManager.assign_user(user=project.owner, project=project)
