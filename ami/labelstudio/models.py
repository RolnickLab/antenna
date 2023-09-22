import logging
import pathlib

from django.db import models
from django.utils.text import slugify
from rest_framework.renderers import JSONRenderer

import ami.utils
from ami.main.models import SourceImageCollection

logger = logging.getLogger(__name__)


class LabelStudioConfig(models.Model):
    """
    Configuration for the integration with Label Studio webhooks.
    """

    project_id = models.PositiveIntegerField(null=True, blank=True)
    base_url = models.CharField(max_length=255, null=True, blank=True)

    # @TODO: encrypt this field and use Django ReadOnlyPasswordHashField
    access_token = models.CharField(max_length=255, null=True, blank=True)

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    task_collection = models.ForeignKey(
        SourceImageCollection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # This could also be a JSON field and use the S3Config class
    s3_key_id = models.CharField(max_length=255, null=True, blank=True)
    # @TODO: encrypt this field and use Django ReadOnlyPasswordHashField
    s3_key_secret = models.CharField(max_length=255, null=True, blank=True)
    s3_endpoint = models.CharField(max_length=1024, null=True, blank=True)
    s3_uri = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Label Studio Config {self.pk}"

    def task_bucket_config(self):
        """
        S3 configuration for storing tasks that are imported to Label Studio.
        """
        if not self.s3_uri or not self.s3_key_id or not self.s3_key_secret:
            raise ValueError("S3 URI, key ID and key secret must be set")

        bucket, prefix = ami.utils.s3.split_uri(self.s3_uri)
        return ami.utils.s3.S3Config(
            bucket_name=bucket,
            prefix=prefix,
            access_key_id=self.s3_key_id,
            secret_access_key=self.s3_key_secret,
            endpoint_url=self.s3_endpoint,
        )

    def write_tasks(self):
        """
        Serialize and write tasks to S3.

        :param collection: Source image collection
        """
        from ami.labelstudio.serializers import LabelStudioSourceImageSerializer

        if not self.task_collection:
            raise ValueError("Task collection must be set")

        bucket_config = self.task_bucket_config()

        # Setup JSON renderer from Django REST Framework
        renderer = JSONRenderer()

        # Render and write tasks as individual JSON files to S3
        count = 0
        for task in self.task_collection.images.all():
            # Serialize task
            serialized_task = LabelStudioSourceImageSerializer(task, many=False).data
            task_json = renderer.render(serialized_task, renderer_context={"indent": 2})

            # Use the original filename as the key, made path safe
            original_path = str(pathlib.Path(task.path).with_suffix(""))
            original_path = original_path.replace("/", "-")
            key = slugify(original_path) + ".json"
            logger.info(f"Publishing task to S3: {key}")

            # The subdir is specified as the prefix in the S3 URI
            result = ami.utils.s3.write_file(
                config=bucket_config,
                key=key,
                body=task_json,
            )
            if result:
                count += 1
        return count
