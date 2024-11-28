import logging

from django.conf import settings
from django.db import transaction

from ami.main.models import Project

from .main import (
    create_captures_from_files,
    create_occurrences_from_frame_data,
    create_taxa,
    setup_test_project,
    update_site_settings,
)

logger = logging.getLogger(__name__)


# Signal receiver function
def setup_complete_test_project(sender, **kwargs):
    # Test if any project exists or if force is set
    if Project.objects.exists() and not kwargs.get("force", False):
        return

    with transaction.atomic():
        update_site_settings(domain=settings.EXTERNAL_HOSTNAME)
        project, deployment = setup_test_project(reuse=True)
        frame_data = create_captures_from_files(deployment)
        taxa_list = create_taxa(project)
        create_occurrences_from_frame_data(frame_data, taxa_list=taxa_list)
        logger.info(f"Created test project {project}")
