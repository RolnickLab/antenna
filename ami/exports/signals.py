import logging

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import DataExport

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender=DataExport)
def delete_exported_file(sender, instance, **kwargs):
    """
    Deletes the exported file when the DataExport instance is deleted.
    """

    file_url = instance.file_url

    if file_url:
        try:
            relative_path = file_url.replace(settings.MEDIA_URL, "").lstrip("/")
            if default_storage.exists(relative_path):
                default_storage.delete(relative_path)
                logger.info(f"Deleted export file: {relative_path}")

        except Exception as e:
            logger.error(f"Error deleting export file {relative_path}: {e}")
