import logging

from celery import shared_task
from django.core.files.storage import default_storage
from django.core.mail import send_mail

from ami.main.models import ExportHistory, Occurrence
from ami.utils.exports import create_dwc_archive
from config.settings.local import DEFAULT_FROM_EMAIL

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def export_occurrences_task(self, occurrence_ids=None, user_email=None, base_url=None):
    """
    Celery task for exporting occurrences asynchronously to MinIO.
    """

    try:
        occurrences = Occurrence.objects.filter(id__in=occurrence_ids)
        file_path = create_dwc_archive(occurrences)
        task_id = self.request.id
        # Generate a unique filename for MinIO storage
        file_name = f"{task_id}.zip"
        minio_path = f"exports/{file_name}"  # Save under 'exports/' folder in MinIO

        # Upload file to MinIO storage
        with open(file_path, "rb") as f:
            default_storage.save(minio_path, f)

        # Get public URL of the stored file
        file_url = f"{base_url}{default_storage.url(minio_path)}"
        logger.info(f"Export completed: {file_url}")
        # Update export history
        ExportHistory.objects.filter(task_id=task_id).update(status="completed", file_url=file_url)
        send_mail(
            subject="Your Occurrence Export is Ready!",
            message=f"""Hello,\n\nYour occurrence data export is complete!
            You can download the file here:\n{file_url}\n\nThank you!""",
            from_email=DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        logger.info(f"Email sent to {user_email} with download link.")
        return {"status": "completed", "file_url": file_url}

    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        ExportHistory.objects.filter(task_id=self.request.id).update(status="failed")
        self.retry(exc=e, countdown=60, max_retries=3)  # Retry up to 3 times
