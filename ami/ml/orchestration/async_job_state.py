"""
Task state management for job progress tracking using Redis.
"""

import logging
from dataclasses import dataclass

from django.core.cache import cache

logger = logging.getLogger(__name__)


@dataclass
class JobStateProgress:
    """Progress snapshot for a job stage tracked in Redis."""

    remaining: int = 0
    total: int = 0
    processed: int = 0
    percentage: float = 0.0
    failed: int = 0


def _lock_key(job_id: int) -> str:
    return f"job:{job_id}:process_results_lock"


class AsyncJobStateManager:
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
        self._failed_key = f"job:{job_id}:failed_images"

    def initialize_job(self, image_ids: list[str]) -> None:
        """
        Initialize job tracking with a list of image IDs to process.

        Args:
            image_ids: List of image IDs that need to be processed
        """
        for stage in self.STAGES:
            cache.set(self._get_pending_key(stage), image_ids, timeout=self.TIMEOUT)

        # Initialize failed images set for process stage only
        cache.set(self._failed_key, set(), timeout=self.TIMEOUT)

        cache.set(self._total_key, len(image_ids), timeout=self.TIMEOUT)

    def _get_pending_key(self, stage: str) -> str:
        return f"{self._pending_key}:{stage}"

    def update_state(
        self,
        processed_image_ids: set[str],
        stage: str,
        request_id: str,
        failed_image_ids: set[str] | None = None,
    ) -> None | JobStateProgress:
        """
        Update the task state with newly processed images.

        Args:
            processed_image_ids: Set of image IDs that have just been processed
            stage: The processing stage ("process" or "results")
            request_id: Unique identifier for this processing request
            detections_count: Number of detections to add to cumulative count
            classifications_count: Number of classifications to add to cumulative count
            captures_count: Number of captures to add to cumulative count
            failed_image_ids: Set of image IDs that failed processing (optional)
        """
        # Create a unique lock key for this job
        lock_key = _lock_key(self.job_id)
        lock_timeout = 360  # 6 minutes (matches task time_limit)
        lock_acquired = cache.add(lock_key, request_id, timeout=lock_timeout)
        if not lock_acquired:
            return None

        try:
            # Update progress tracking in Redis
            progress_info = self._commit_update(processed_image_ids, stage, failed_image_ids)
            return progress_info
        finally:
            # Always release the lock when done
            current_lock_value = cache.get(lock_key)
            # Only delete if we still own the lock (prevents race condition)
            if current_lock_value == request_id:
                cache.delete(lock_key)
                logger.debug(f"Released lock for job {self.job_id}, task {request_id}")

    def get_progress(self, stage: str) -> JobStateProgress | None:
        """Read-only progress snapshot for the given stage. Does not acquire a lock or mutate state."""
        pending_images = cache.get(self._get_pending_key(stage))
        total_images = cache.get(self._total_key)
        if pending_images is None or total_images is None:
            return None
        remaining = len(pending_images)
        processed = total_images - remaining
        percentage = float(processed) / total_images if total_images > 0 else 1.0
        failed_set = cache.get(self._failed_key) or set()
        return JobStateProgress(
            remaining=remaining,
            total=total_images,
            processed=processed,
            percentage=percentage,
            failed=len(failed_set),
        )

    def _commit_update(
        self,
        processed_image_ids: set[str],
        stage: str,
        failed_image_ids: set[str] | None = None,
    ) -> JobStateProgress | None:
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

        # Update failed images set if provided
        if failed_image_ids:
            existing_failed = cache.get(self._failed_key) or set()
            updated_failed = existing_failed | failed_image_ids  # Union to prevent duplicates
            cache.set(self._failed_key, updated_failed, timeout=self.TIMEOUT)
            failed_set = updated_failed
        else:
            failed_set = cache.get(self._failed_key) or set()

        failed_count = len(failed_set)

        logger.info(
            f"Pending images from Redis for job {self.job_id} {stage}: "
            f"{remaining}/{total_images}: {percentage*100}%"
        )

        return JobStateProgress(
            remaining=remaining,
            total=total_images,
            processed=processed,
            percentage=percentage,
            failed=failed_count,
        )

    def cleanup(self) -> None:
        """
        Delete all Redis keys associated with this job.
        """
        for stage in self.STAGES:
            cache.delete(self._get_pending_key(stage))
        cache.delete(self._failed_key)
        cache.delete(self._total_key)
