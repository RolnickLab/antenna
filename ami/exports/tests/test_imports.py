import logging

from django.test import TestCase

logger = logging.getLogger(__name__)


class DataImportTests(TestCase):
    """
    Test importing from saved PipelineResponse json files.

    Uses fixtures in `ami/exports/tests/fixtures/*.json`.
    """

    def setUp(self):
        from ami.main.models import Project, get_or_create_default_device, get_or_create_default_research_site

        # Create an empty project
        self.project = Project.objects.create(name="Imported Project", create_defaults=False)

        # For some reason test _tear down_ fails if these don't exist!
        # Even if the tests pass.
        get_or_create_default_device(self.project)
        get_or_create_default_research_site(self.project)

    def test_import_pipeline_results(self):
        """Test importing from API JSON."""

        results_fpath = "ami/exports/tests/fixtures/pipeline_response-complete_local_project.json"

        from django.core.management import call_command

        call_command("import_pipeline_results", results_fpath, project=self.project.pk)
