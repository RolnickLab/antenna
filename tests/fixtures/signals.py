from django.conf import settings
from django.db import transaction

from ami.main.models import Project, group_images_into_events

from .main import create_captures, create_occurrences, create_taxa, setup_test_project, update_site_settings


# Signal receiver function
def setup_complete_test_project(sender, **kwargs):
    # Test if any project exists or if force is set
    if Project.objects.exists() and not kwargs.get("force", False):
        return

    with transaction.atomic():
        update_site_settings(domain=settings.EXTERNAL_HOSTNAME)
        project, deployment = setup_test_project(reuse=False)
        create_captures(deployment)
        group_images_into_events(deployment)
        taxa_list = create_taxa(project)
        for taxon in taxa_list.taxa.all():
            create_occurrences(deployment=deployment, taxon=taxon, num=3)
