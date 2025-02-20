import logging

from ami.main.models import Project
from ami.users.roles import create_roles_for_project

logger = logging.getLogger(__name__)


def create_roles(sender, **kwargs):
    """Creates predefined roles with specific permissions ."""

    logger.info("Creating roles")
    for project in Project.objects.all():
        create_roles_for_project(project)
