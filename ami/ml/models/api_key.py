from django.db import models
from rest_framework_api_key.models import AbstractAPIKey


class ProcessingServiceAPIKey(AbstractAPIKey):
    processing_service = models.ForeignKey(
        "ml.ProcessingService",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "Processing Service API Key"
        verbose_name_plural = "Processing Service API Keys"
