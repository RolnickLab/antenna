from django.conf import settings
from django.core.management.base import BaseCommand, CommandError  # noqa

from ....utils import s3 as s3_utils
from ...models import Deployment, SourceImage


class Command(BaseCommand):
    r"""Import source images from s3 bucket configured for Deployment."""

    help = "Import trap data from a Deployment's data source"

    def add_arguments(self, parser):
        parser.add_argument("deployment_id", type=int)

    def handle(self, *args, **options):
        deployment_id = options["deployment_id"]
        deployment = Deployment.objects.get(id=deployment_id)
        self.import_source_images(deployment)

    def import_source_images(self, deployment):
        """Import source images from s3 bucket configured for Deployment.

        @TODO move this to a Deployment method, or management/main.py
        """

        data_source = deployment.data_source
        assert data_source, f"Deployment {deployment.name} has no data source configured"

        if not data_source.startswith("s3://"):
            raise CommandError(f"Only s3:// data sources are currently supported, not {data_source}")

        bucket_name, prefix = s3_utils.split_uri(data_source)
        s3_config = s3_utils.S3Config(
            bucket_name=bucket_name,
            prefix=prefix,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )
        objects = s3_utils.list_files(s3_config)
        for obj in objects:
            source_image, created = SourceImage.objects.get_or_create(
                deployment=deployment,
                path=obj.key,
                defaults={
                    "last_modified": obj.last_modified,
                    "size": obj.size,
                    "checksum": obj.e_tag.strip('"'),
                    "checksum_algorithm": obj.checksum_algorithm,
                },
            )
            if created:
                print(f"Created SourceImage {source_image.pk} {source_image.path}")
            else:
                print(f"SourceImage {source_image.pk} {source_image.path} already exists")
