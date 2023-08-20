import time

from django.core.management.base import BaseCommand, CommandError  # noqa

from ...models import Deployment, Device, Event, Project, Site, SourceImage, TaxaList, Taxon


class Command(BaseCommand):
    r"""Load minimum example data needed for development and tests."""

    help = "Load minimum example data needed for development and tests"

    def add_arguments(self, parser):
        # Add option to delete existing data
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete existing data before loading new data",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            self.stdout.write(self.style.WARNING("! Deleting existing data !"))
            time.sleep(2)
            Project.objects.all().delete()
            Deployment.objects.all().delete()
            TaxaList.objects.all().delete()
            Taxon.objects.all().delete()
            Event.objects.all().delete()
            SourceImage.objects.all().delete()

        project, _ = Project.objects.get_or_create(name="Default Project")
        research_site, _ = Site.objects.get_or_create(name="Default Research Site")
        device, _ = Device.objects.get_or_create(name="Default Device Config")
        deployment, _ = Deployment.objects.get_or_create(
            project=project, name="Default Deployment", defaults={"device": device, "resarch_site": research_site}
        )

        taxa_list, _ = TaxaList.objects.get_or_create(name="Default Taxa List")

        # Create several butterfly species and parents and assign them to the taxa list
        parent_taxon, _ = Taxon.objects.get_or_create(name="Lepidoptera")
        parent_taxon.lists.set([taxa_list])

        for name in ["Pieris rapae", "Pieris napi", "Pieris brassicae"]:
            taxon, _ = Taxon.objects.get_or_create(name=name, parent=parent_taxon)
            taxon.lists.set([taxa_list])

        # num_captures_imported = deployment.import_captures()
        # msg = f"Imported {num_captures_imported} source images for {deployment}"
        # self.stdout.write(self.style.SUCCESS(msg))
