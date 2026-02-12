"""
Task state management for job progress tracking using Redis.
"""

import logging
from collections import namedtuple

from django.core.cache import cache

logger = logging.getLogger(__name__)


# Define a namedtuple for a TaskProgress with the image counts
TaskProgress = namedtuple("TaskProgress", ["remaining", "total", "processed", "percentage"])


def _lock_key(job_id: int) -> str:
    return f"job:{job_id}:process_results_lock"


class TaskStateManager:
    """
    Manages job progress tracking state in Redis.

    Tracks pending images for jobs to calculate progress percentages
    as workers process images asynchronously.
    """

    TIMEOUT = 86400 * 7  # 7 days in seconds
    STAGES = ["process", "results"]

    def __init__(self, job_id: int):
        """
        Initialize the task state manager for a specific job.

        Args:
            job_id: The job primary key
        """
        self.job_id = job_id
        self._pending_key = f"job:{job_id}:pending_images"
        self._total_key = f"job:{job_id}:pending_images_total"

    def initialize_job(self, image_ids: list[str]) -> None:
        """
        Initialize job tracking with a list of image IDs to process.

        Args:
            image_ids: List of image IDs that need to be processed
        """
        for stage in self.STAGES:
            cache.set(self._get_pending_key(stage), image_ids, timeout=self.TIMEOUT)

        cache.set(self._total_key, len(image_ids), timeout=self.TIMEOUT)

    def _get_pending_key(self, stage: str) -> str:
        return f"{self._pending_key}:{stage}"

    def update_state(
        self,
        processed_image_ids: set[str],
        stage: str,
        request_id: str,
    ) -> None | TaskProgress:
        """
        Update the task state with newly processed images.

        Args:
            processed_image_ids: Set of image IDs that have just been processed
        """
        # Create a unique lock key for this job
        lock_key = _lock_key(self.job_id)
        lock_timeout = 360  # 6 minutes (matches task time_limit)
        lock_acquired = cache.add(lock_key, request_id, timeout=lock_timeout)
        if not lock_acquired:
            return None

        try:
            # Update progress tracking in Redis
            progress_info = self._get_progress(processed_image_ids, stage)
            return progress_info
        finally:
            # Always release the lock when done
            current_lock_value = cache.get(lock_key)
            # Only delete if we still own the lock (prevents race condition)
            if current_lock_value == request_id:
                cache.delete(lock_key)
                logger.debug(f"Released lock for job {self.job_id}, task {request_id}")

    def get_progress(self, stage: str) -> TaskProgress | None:
        """Read-only progress snapshot for the given stage. Does not acquire a lock or mutate state."""
        pending_images = cache.get(self._get_pending_key(stage))
        total_images = cache.get(self._total_key)
        if pending_images is None or total_images is None:
            return None
        remaining = len(pending_images)
        processed = total_images - remaining
        percentage = float(processed) / total_images if total_images > 0 else 1.0
        return TaskProgress(remaining=remaining, total=total_images, processed=processed, percentage=percentage)

    def _get_progress(self, processed_image_ids: set[str], stage: str) -> TaskProgress | None:
        """
        Update pending images and return progress. Must be called under lock.

        Removes processed_image_ids from the pending set and persists the update.
        """
        pending_images = cache.get(self._get_pending_key(stage))
        total_images = cache.get(self._total_key)
        if pending_images is None or total_images is None:
            return None
        remaining_images = [img_id for img_id in pending_images if img_id not in processed_image_ids]
        assert len(pending_images) >= len(remaining_images)
        cache.set(self._get_pending_key(stage), remaining_images, timeout=self.TIMEOUT)

        remaining = len(remaining_images)
        processed = total_images - remaining
        percentage = float(processed) / total_images if total_images > 0 else 1.0
        logger.info(
            f"Pending images from Redis for job {self.job_id} {stage}: "
            f"{remaining}/{total_images}: {percentage*100}%"
        )

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
        for stage in self.STAGES:
            cache.delete(self._get_pending_key(stage))
        cache.delete(self._total_key)
