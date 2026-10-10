"""
Storage sources and manual capture uploads.

Models are declared here but remain in the ``main`` app. Related models are
referenced by string label so this module never imports ``ami.main.models``,
which imports this one.
"""

from typing import TYPE_CHECKING, final

from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.template.defaultfilters import filesizeformat

import ami.tasks
import ami.utils
from ami.base.models import BaseModel

if TYPE_CHECKING:
    from ami.main.models import Deployment


@final
class S3StorageSource(BaseModel):
    """
    Per-deployment configuration for an S3 bucket.
    """

    name = models.CharField(max_length=255)
    bucket = models.CharField(max_length=255)
    region = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="AWS region (e.g., 'us-east-1', 'eu-west-1'). Leave blank for Swift/MinIO storage.",
    )
    prefix = models.CharField(max_length=255, blank=True)
    access_key = models.TextField()
    secret_key = models.TextField()
    endpoint_url = models.CharField(max_length=255, blank=True, null=True)
    public_base_url = models.CharField(max_length=255, blank=True, null=True)
    total_size = models.BigIntegerField(null=True, blank=True)
    total_files = models.BigIntegerField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    # last_check_duration = models.DurationField(null=True, blank=True)
    # use_signed_urls = models.BooleanField(default=False)
    project = models.ForeignKey("main.Project", on_delete=models.SET_NULL, null=True, related_name="storage_sources")
    # @TODO allow multiple projects to share the same S3StorageSource

    deployments: models.QuerySet["Deployment"]

    @property
    def config(self) -> ami.utils.s3.S3Config:
        return ami.utils.s3.S3Config(
            bucket_name=self.bucket,
            region=self.region,
            prefix=self.prefix,
            access_key_id=self.access_key,
            secret_access_key=self.secret_key,
            endpoint_url=self.endpoint_url,
            public_base_url=self.public_base_url,
        )

    def deployments_count(self) -> int:
        return self.deployments.count()

    def total_files_indexed(self) -> int:
        return self.deployments.aggregate(total_files=models.Sum("data_source_total_files"))["total_files"]

    def total_size_indexed(self) -> int:
        return self.deployments.aggregate(total_size=models.Sum("data_source_total_size"))["total_size"]

    def total_size_indexed_display(self) -> str:
        return filesizeformat(self.total_size_indexed())

    def total_captures_indexed(self) -> int:
        return self.deployments.aggregate(total_captures=models.Sum("captures_count"))["total_captures"]

    def list_files(self, limit=None):
        """Recursively list files in the bucket/prefix."""

        return ami.utils.s3.list_files_paginated(self.config, limit=limit)

    def count_files(self):
        """Count & save the number of files in the bucket/prefix."""

        count = ami.utils.s3.count_files_paginated(self.config)
        self.total_files = count
        self.save()
        return count

    def calculate_size(self):
        """Calculate the total size and count of all files in the bucket/prefix."""

        sizes = [obj["Size"] for obj, _num_files_checked in self.list_files() if obj]  # type: ignore
        size = sum(sizes)
        count = len(sizes)
        self.total_size = size
        self.total_files = count
        self.save()
        return size

    def uri(self, path: str | None = None):
        """Return the full URI for the given path."""

        full_path = "/".join(str(part).strip("/") for part in [self.bucket, self.prefix, path] if part)
        return f"s3://{full_path}"

    def public_url(self, path: str):
        """Return the public URL for the given path."""

        return ami.utils.s3.public_url(self.config, path)

    def test_connection(
        self, subdir: str | None = None, regex_filter: str | None = None
    ) -> ami.utils.s3.ConnectionTestResult:
        """Test the connection to the S3 bucket."""

        return ami.utils.s3.test_connection(self.config, subdir=subdir, regex_filter=regex_filter)

    def save(self, *args, **kwargs):
        # If public_base_url has changed, update the urls for all source images
        if self.pk:
            old = S3StorageSource.objects.get(pk=self.pk)
            if old.public_base_url != self.public_base_url:
                for deployment in self.deployments.all():
                    ami.tasks.update_public_urls.delay(deployment.pk, self.public_base_url)
        super().save(*args, **kwargs)


def upload_to_with_deployment(instance, filename: str) -> str:
    """Nest uploads under subdir for a deployment."""
    return f"example_captures/{instance.deployment.pk}/{filename}"


@final
class SourceImageUpload(BaseModel):
    """
    A manually uploaded image that has not yet been imported.

    The SourceImageViewSet will create a SourceImage from the uploaded file and delete the upload.
    """

    project_accessor = "deployment__project"
    image = models.ImageField(upload_to=upload_to_with_deployment)
    user = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    deployment = models.ForeignKey(
        "main.Deployment", on_delete=models.CASCADE, related_name="manually_uploaded_captures"
    )
    source_image = models.OneToOneField(
        "main.SourceImage", on_delete=models.CASCADE, null=True, blank=True, related_name="upload"
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # @TODO Use a "dirty" flag to mark the deployment as having new uploads, needs refresh
        self.deployment.save()


@receiver(pre_delete, sender=SourceImageUpload)
def delete_source_image(sender, instance, **kwargs):
    """
    A SourceImageUpload are automatically deleted when deleting a SourceImage because of the CASCADE setting.
    However the SourceImage needs to be deleted using a signal when deleting a SourceImageUpload.
    """
    if instance.source_image:
        # Disconnect the SourceImage from the upload to prevent recursion error
        source_image = instance.source_image
        instance.source_image = None
        instance.save()
        source_image.delete()
    # @TODO Use a "dirty" flag to mark the deployment as having new uploads, needs refresh
    instance.deployment.save()
