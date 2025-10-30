"""
Task state management for job progress tracking using Redis.
"""

import logging
from collections import namedtuple

from django.core.cache import cache

logger = logging.getLogger(__name__)


# Define a namedtuple for a TaskProgress with the image counts
TaskProgress = namedtuple("TaskProgress", ["remaining", "total", "processed", "percentage"])


class TaskStateManager:
    """
    Manages job progress tracking state in Redis.

    Tracks pending images for jobs to calculate progress percentages
    as workers process images asynchronously.
    """

    TIMEOUT = 86400 * 7  # 7 days in seconds

    def __init__(self, job_id: int):
        """
        Initialize the task state manager for a specific job.

        Args:
            job_id: The job primary key
        """
        self.job_id = job_id
        self._pending_key = f"job:{job_id}:pending_images"  # noqa E231
        self._total_key = f"job:{job_id}:pending_images_total"  # noqa E231

    def initialize_job(self, image_ids: list[str]) -> None:
        """
        Initialize job tracking with a list of image IDs to process.

        Args:
            image_ids: List of image IDs that need to be processed
        """
        cache.set(self._pending_key, image_ids, timeout=self.TIMEOUT)
        cache.set(self._total_key, len(image_ids), timeout=self.TIMEOUT)

    def mark_images_processed(self, processed_image_ids: set[str]) -> None:
        """
        Mark a set of images as processed by removing them from pending list.

        Args:
            processed_image_ids: Set of image IDs that have been processed
        """
        pending_images = cache.get(self._pending_key)
        if pending_images is None:
            return

        remaining_images = [img_id for img_id in pending_images if img_id not in processed_image_ids]

        cache.set(self._pending_key, remaining_images, timeout=self.TIMEOUT)

    def get_progress(self) -> TaskProgress | None:
        """
        Get current progress information for the job.

        Returns:
            TaskProgress namedtuple with fields:
                - remaining: Number of images still pending (or None if not tracked)
                - total: Total number of images (or None if not tracked)
                - processed: Number of images processed (or None if not tracked)
                - percentage: Progress as float 0.0-1.0 (or None if not tracked)
        """
        pending_images = cache.get(self._pending_key)
        total_images = cache.get(self._total_key)

        if pending_images is None or total_images is None:
            return None

        remaining = len(pending_images)
        processed = total_images - remaining
        percentage = float(processed) / total_images if total_images > 0 else 1.0
        logger.info(f"Pending images from Redis for job {self.job_id}: " f"{remaining}/{total_images}")

        return TaskProgress(
            remaining=remaining,
            total=total_images,
            processed=processed,
            percentage=percentage,
        )

    def cleanup(self) -> None:
        """
        Delete all Redis keys associated with this job.
        """
        cache.delete(self._pending_key)
        cache.delete(self._total_key)
