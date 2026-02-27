"""
Internal progress tracking for async (NATS) job processing, backed by Redis.

Multiple Celery workers process image batches concurrently and report progress
here using Redis native set operations. No locking is required because:

  - SREM (remove processed images from pending set) is atomic per call
  - SADD (add to failed set) is atomic per call
  - SCARD (read set size) is O(1) without deserializing members

Workers update state independently via a single Redis pipeline round-trip.
This module is purely internal — nothing outside the worker pipeline reads
from it directly.

How this relates to the Job model (ami/jobs/models.py):

  The **Job model** is the primary, external-facing record. It is what users see
  in the UI, what external APIs interact with (listing open jobs, fetching tasks
  to process), and what persists as history in the CMS. It has two relevant fields:

  - **Job.status** (JobState enum) — lifecycle state (CREATED → STARTED → SUCCESS/FAILURE)
  - **Job.progress** (JobProgress JSONB) — detailed stage progress with params
    like detections, classifications, captures counts

  This Redis layer exists only because concurrent NATS workers need atomic
  counters that PostgreSQL row locks would serialize too aggressively. After each
  batch, _update_job_progress() in ami/jobs/tasks.py copies the Redis snapshot
  into the Job model, which is the source of truth for everything external.

Flow: NATS result → AsyncJobStateManager.update_state() (Redis, internal)
      → _update_job_progress() (writes to Job model) → UI / API reads Job
"""

import logging
from dataclasses import dataclass

from django_redis import get_redis_connection
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@dataclass
class JobStateProgress:
    """
    Progress snapshot for a job stage, read from Redis.

    All counts refer to source images (captures), not detections or occurrences.
    Currently specific to ML pipeline jobs — if other job types are made available
    for external processing, the unit of work ("source image") and failure semantics
    may need to be generalized.
    """

    remaining: int = 0  # source images not yet processed in this stage
    total: int = 0  # total source images in the job
    processed: int = 0  # source images completed (success + failed)
    percentage: float = 0.0  # processed / total
    failed: int = 0  # source images that returned an error from the processing service


class AsyncJobStateManager:
    """
    Manages real-time job progress in Redis for concurrent NATS workers.

    Each job has per-stage pending image sets and a shared failed image set,
    all stored as native Redis sets. Workers update state via atomic SREM/SADD
    commands — no locking needed.

    The results are ephemeral — _update_job_progress() in ami/jobs/tasks.py
    copies each snapshot into the persistent Job.progress JSONB field.
    """

    TIMEOUT = 86400 * 7  # 7 days in seconds
    STAGES = ["process", "results"]

    def __init__(self, job_id: int):
        self.job_id = job_id
        self._pending_key = f"job:{job_id}:pending_images"
        self._total_key = f"job:{job_id}:pending_images_total"
        self._failed_key = f"job:{job_id}:failed_images"

    def _get_redis(self):
        return get_redis_connection("default")

    def initialize_job(self, image_ids: list[str]) -> None:
        """
        Initialize job tracking with a list of image IDs to process.

        Args:
            image_ids: List of image IDs that need to be processed
        """
        try:
            redis = self._get_redis()
            with redis.pipeline() as pipe:
                for stage in self.STAGES:
                    pending_key = self._get_pending_key(stage)
                    pipe.delete(pending_key)
                    if image_ids:
                        pipe.sadd(pending_key, *image_ids)
                        pipe.expire(pending_key, self.TIMEOUT)
                pipe.delete(self._failed_key)
                pipe.set(self._total_key, len(image_ids), ex=self.TIMEOUT)
                pipe.execute()
        except RedisError as e:
            logger.error(f"Redis error initializing job {self.job_id}: {e}")
            raise

    def _get_pending_key(self, stage: str) -> str:
        return f"{self._pending_key}:{stage}"

    def update_state(
        self,
        processed_image_ids: set[str],
        stage: str,
        failed_image_ids: set[str] | None = None,
    ) -> "JobStateProgress | None":
        """
        Atomically update job state with newly processed images.

        Uses a Redis pipeline (single round-trip). SREM and SADD are each
        individually atomic; the pipeline batches them with SCARD/GET to avoid
        multiple round-trips. Workers can call this concurrently — no lock needed.

        Args:
            processed_image_ids: Set of image IDs that have just been processed
            stage: The processing stage ("process" or "results")
            failed_image_ids: Set of image IDs that failed processing (optional)

        Returns:
            JobStateProgress snapshot, or None if Redis state is missing
            (job expired or not yet initialized).
        """
        try:
            redis = self._get_redis()
            pending_key = self._get_pending_key(stage)

            with redis.pipeline() as pipe:
                if processed_image_ids:
                    pipe.srem(pending_key, *processed_image_ids)
                if failed_image_ids:
                    pipe.sadd(self._failed_key, *failed_image_ids)
                    pipe.expire(self._failed_key, self.TIMEOUT)
                pipe.scard(pending_key)
                pipe.scard(self._failed_key)
                pipe.get(self._total_key)
                results = pipe.execute()
        except RedisError as e:
            logger.error(f"Redis error updating job {self.job_id} state: {e}")
            return None

        # Last 3 results are always scard(pending), scard(failed), get(total)
        # regardless of whether SREM/SADD appear at the front.
        remaining, failed_count, total_raw = results[-3], results[-2], results[-1]

        if total_raw is None:
            return None

        total = int(total_raw)
        processed = total - remaining
        percentage = float(processed) / total if total > 0 else 1.0

        logger.info(
            f"Pending images from Redis for job {self.job_id} {stage}: " f"{remaining}/{total}: {percentage*100}%"
        )

        return JobStateProgress(
            remaining=remaining,
            total=total,
            processed=processed,
            percentage=percentage,
            failed=failed_count,
        )

    def get_progress(self, stage: str) -> "JobStateProgress | None":
        """Read-only progress snapshot for the given stage."""
        try:
            redis = self._get_redis()
            pending_key = self._get_pending_key(stage)

            with redis.pipeline() as pipe:
                pipe.scard(pending_key)
                pipe.scard(self._failed_key)
                pipe.get(self._total_key)
                remaining, failed_count, total_raw = pipe.execute()
        except RedisError as e:
            logger.error(f"Redis error reading job {self.job_id} progress: {e}")
            return None

        if total_raw is None:
            return None

        total = int(total_raw)
        processed = total - remaining
        percentage = float(processed) / total if total > 0 else 1.0

        return JobStateProgress(
            remaining=remaining,
            total=total,
            processed=processed,
            percentage=percentage,
            failed=failed_count,
        )

    def cleanup(self) -> None:
        """
        Delete all Redis keys associated with this job.
        """
        try:
            redis = self._get_redis()
            keys = [self._get_pending_key(stage) for stage in self.STAGES]
            keys += [self._failed_key, self._total_key]
            redis.delete(*keys)
        except RedisError as e:
            logger.warning(f"Redis error cleaning up job {self.job_id}: {e}")
