"""
Task state management for job progress tracking using Redis.
"""

import logging
from collections import namedtuple

from django.core.cache import cache

logger = logging.getLogger(__name__)


# Define a namedtuple for a TaskProgress with the image counts
TaskProgress = namedtuple(
    "TaskProgress", ["remaining", "total", "processed", "percentage", "detections", "classifications"]
)


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
        self._detections_key = f"job:{job_id}:total_detections"
        self._classifications_key = f"job:{job_id}:total_classifications"

    def initialize_job(self, image_ids: list[str]) -> None:
        """
        Initialize job tracking with a list of image IDs to process.

        Args:
            image_ids: List of image IDs that need to be processed
        """
        for stage in self.STAGES:
            cache.set(self._get_pending_key(stage), image_ids, timeout=self.TIMEOUT)

        cache.set(self._total_key, len(image_ids), timeout=self.TIMEOUT)

        # Initialize detection and classification counters
        cache.set(self._detections_key, 0, timeout=self.TIMEOUT)
        cache.set(self._classifications_key, 0, timeout=self.TIMEOUT)

    def _get_pending_key(self, stage: str) -> str:
        return f"{self._pending_key}:{stage}"

    def update_state(
        self,
        processed_image_ids: set[str],
        stage: str,
        request_id: str,
        detections_count: int = 0,
        classifications_count: int = 0,
    ) -> None | TaskProgress:
        """
        Update the task state with newly processed images.

        Args:
            processed_image_ids: Set of image IDs that have just been processed
            stage: The processing stage ("process" or "results")
            request_id: Unique identifier for this processing request
            detections_count: Number of detections to add to cumulative count
            classifications_count: Number of classifications to add to cumulative count
        """
        # Create a unique lock key for this job
        lock_key = f"job:{self.job_id}:process_results_lock"
        lock_timeout = 360  # 6 minutes (matches task time_limit)
        lock_acquired = cache.add(lock_key, request_id, timeout=lock_timeout)
        if not lock_acquired:
            return None

        try:
            # Update progress tracking in Redis
            progress_info = self._get_progress(processed_image_ids, stage, detections_count, classifications_count)
            return progress_info
        finally:
            # Always release the lock when done
            current_lock_value = cache.get(lock_key)
            # Only delete if we still own the lock (prevents race condition)
            if current_lock_value == request_id:
                cache.delete(lock_key)
                logger.debug(f"Released lock for job {self.job_id}, task {request_id}")

    def _get_progress(
        self, processed_image_ids: set[str], stage: str, detections_count: int = 0, classifications_count: int = 0
    ) -> TaskProgress | None:
        """
        Get current progress information for the job.

        Returns:
            TaskProgress namedtuple with fields:
                - remaining: Number of images still pending (or None if not tracked)
                - total: Total number of images (or None if not tracked)
                - processed: Number of images processed (or None if not tracked)
                - percentage: Progress as float 0.0-1.0 (or None if not tracked)
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

        # Update cumulative detection and classification counts
        current_detections = cache.get(self._detections_key, 0)
        current_classifications = cache.get(self._classifications_key, 0)

        new_detections = current_detections + detections_count
        new_classifications = current_classifications + classifications_count

        cache.set(self._detections_key, new_detections, timeout=self.TIMEOUT)
        cache.set(self._classifications_key, new_classifications, timeout=self.TIMEOUT)

        logger.info(
            f"Pending images from Redis for job {self.job_id} {stage}: "
            f"{remaining}/{total_images}: {percentage*100}%"
        )

        return TaskProgress(
            remaining=remaining,
            total=total_images,
            processed=processed,
            percentage=percentage,
            detections=new_detections,
            classifications=new_classifications,
        )

    def cleanup(self) -> None:
        """
        Delete all Redis keys associated with this job.
        """
        for stage in self.STAGES:
            cache.delete(self._get_pending_key(stage))
        cache.delete(self._total_key)
        cache.delete(self._detections_key)
        cache.delete(self._classifications_key)
