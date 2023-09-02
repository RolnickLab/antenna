from django.db import models


class LabelStudioConfig(models.Model):
    """
    Configuration for the integration with Label Studio webhooks.
    """

    object_detection_project_id = models.PositiveIntegerField(null=True, blank=True)
    binary_classification_project_id = models.PositiveIntegerField(null=True, blank=True)
    species_classification_project_id = models.PositiveIntegerField(null=True, blank=True)

    access_token = models.CharField(max_length=255, null=True, blank=True)
    base_url = models.CharField(max_length=255, null=True, blank=True)

    sync_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
