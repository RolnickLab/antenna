from django.core.management.base import BaseCommand, CommandError  # noqa

from ...models import Deployment


class Command(BaseCommand):
    r"""Import source images from s3 bucket configured for Deployment."""

    help = "Import trap data from a Deployment's data source"

    def add_arguments(self, parser):
        parser.add_argument("deployment_id", type=int)

    def handle(self, *args, **options):
        deployment_id = options["deployment_id"]
        deployment = Deployment.objects.get(id=deployment_id)
        created = deployment.import_captures()
        msg = f"Imported {len(created)} source images for {deployment}"
        self.stdout.write(self.style.SUCCESS(msg))
