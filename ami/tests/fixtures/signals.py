import logging

from django.conf import settings

from ami.main.models import Project

from .main import create_complete_test_project, create_local_admin_user, update_site_settings

logger = logging.getLogger(__name__)


def initialize_demo_project(sender, **kwargs):
    """
    Signal handler to create a demo project after `migrate` is run.
    """
    if not Project.objects.exists():
        update_site_settings(domain=settings.EXTERNAL_HOSTNAME)
        create_complete_test_project()
        create_local_admin_user()
