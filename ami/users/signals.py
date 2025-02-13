from django.db.models.signals import post_migrate
from django.dispatch import receiver

from ami.main.models import Project
from ami.users.roles import create_roles_for_project


@receiver(post_migrate)
def create_roles(sender, **kwargs):
    """Creates predefined roles with specific permissions when the app starts."""

    # Get all Role subclasses dynamically
    for project in Project.objects.all():
        create_roles_for_project(project)
