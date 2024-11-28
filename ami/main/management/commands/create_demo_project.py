import time

from django.core.management.base import BaseCommand

from ami.main.models import Deployment, Detection, Device, Event, Occurrence, Project, SourceImage, TaxaList, Taxon
from ami.ml.models import Algorithm, Pipeline
from ami.tests.fixtures.main import create_complete_test_project, create_local_admin_user


class Command(BaseCommand):
    r"""Create example data needed for development and tests."""

    help = "Create example data needed for development and tests"

    def add_arguments(self, parser):
        # Add option to delete existing data
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete existing data before creating new demo project",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            self.stdout.write(self.style.WARNING("! Deleting existing data !"))
            time.sleep(2)
            for model in [
                Project,
                Device,
                Deployment,
                TaxaList,
                Taxon,
                Event,
                SourceImage,
                Detection,
                Occurrence,
                Algorithm,
                Pipeline,
            ]:
                self.stdout.write(f"Deleting all {model._meta.verbose_name_plural} and related objects")
                model.objects.all().delete()

        self.stdout.write("Creating test project")
        create_complete_test_project()
        create_local_admin_user()
