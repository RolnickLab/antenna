import dataclasses
import datetime
import functools
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from asgiref.sync import async_to_sync, sync_to_async
from celery.signals import task_failure, task_postrun, task_prerun
from django.db import transaction
from redis.exceptions import RedisError

from ami.main.checks.schemas import IntegrityCheckResult
from ami.ml.orchestration.async_job_state import AsyncJobStateManager
from ami.ml.orchestration.nats_queue import TaskQueueManager
from ami.ml.schemas import PipelineResultsError, PipelineResultsResponse
from ami.tasks import default_soft_time_limit, default_time_limit
from config import celery_app

if TYPE_CHECKING:
    from ami.jobs.models import JobState

logger = logging.getLogger(__name__)
# Minimum success rate. Jobs with fewer than this fraction of images
# processed successfully are marked as failed. Also used in MLJob.process_images().
FAILURE_THRESHOLD = 0.5


@celery_app.task(bind=True, soft_time_limit=default_soft_time_limit, time_limit=default_time_limit)
def run_job(self, job_id: int) -> None:
    from ami.jobs.models import Job

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist as e:
        raise e
        # self.retry(exc=e, countdown=1, max_retries=1)
    else:
        job.logger.info(f"Running job {job}")
        try:
            job.run()
        except Exception as e:
            job.logger.error(f'Job #{job.pk} "{job.name}" failed: {e}')
            raise
        else:
            from ami.jobs.models import JobDispatchMode

            job.refresh_from_db()
            if job.dispatch_mode == JobDispatchMode.ASYNC_API and not job.progress.is_complete():
                job.logger.info(f"run_job task exited for job {job}; async results still in-flight via NATS")
            else:
                job.logger.info(f"Finished job {job}")


@celery_app.task(
    bind=True,
    # Retry on transient Redis/connection errors so a single connection reset
    # doesn't flip the job to FAILURE mid-processing. Backoff is capped at 15s
    # (half of NATS ack_wait = TASK_TTR = 30s, see nats_queue.py) so a retry
    # is likely to complete before JetStream redelivers the same payload to
    # ADC. retries stay well below soft_time_limit so they never leak past
    # the task deadline. Terminal failures (e.g. PipelineResultsError
    # validation) are raised from other exception types and not retried here.
    # See RolnickLab/antenna#1219.
    autoretry_for=(RedisError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=15,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=300,  # 5 minutes
    time_limit=360,  # 6 minutes
)
def process_nats_pipeline_result(self, job_id: int, result_data: dict, reply_subject: str) -> None:
    """
    Process a single pipeline result asynchronously.

    This task:
    1. Deserializes the pipeline result
    2. Saves it to the database
    3. Updates progress by removing processed image IDs from Redis
    4. Acknowledges the task via NATS

    Args:
        job_id: The job ID
        result_data: Dictionary containing the pipeline result
        reply_subject: NATS reply subject for acknowledgment
    """
    from ami.jobs.models import Job, JobState  # avoid circular import

    _, t = log_time()

    # Validate with Pydantic - check for error response first
    error_result = None
    if "error" in result_data:
        error_result = PipelineResultsError(**result_data)
        processed_image_ids = {str(error_result.image_id)} if error_result.image_id else set()
        failed_image_ids = processed_image_ids  # Same as processed for errors
        pipeline_result = None
    else:
        pipeline_result = PipelineResultsResponse(**result_data)
        processed_image_ids = {str(img.id) for img in pipeline_result.source_images}
        failed_image_ids = set()  # No failures for successful results

    state_manager = AsyncJobStateManager(job_id)

    try:
        progress_info = state_manager.update_state(
            processed_image_ids, stage="process", failed_image_ids=failed_image_ids
        )
    except RedisError as e:
        # Transient (connection reset, broker blip, timeout). Celery will retry
        # via autoretry_for. We have NOT yet acked NATS here, so if the retry
        # budget runs long enough JetStream may redeliver to ADC (ack_wait =
        # TASK_TTR = 30s, see nats_queue.py); save_results dedupes and SREM is
        # a no-op on replay, so duplication is cosmetic rather than corrupting.
        # Log so the real cause is visible in task logs rather than the
        # misleading "Redis state missing" that users saw in #1219.
        logger.warning(
            f"Transient Redis error updating job {job_id} state (stage=process); Celery will retry: {e}",
            exc_info=True,
        )
        raise

    if not progress_info:
        # State keys genuinely missing (the total-images key returned None).
        # Ack so NATS stops redelivering and fail the job — there's no state
        # left to reconcile against.
        _ack_task_via_nats(reply_subject, logger)
        _fail_job(job_id, "Job state keys not found in Redis (likely cleaned up concurrently)")
        return

    try:
        complete_state = JobState.SUCCESS
        if progress_info.total > 0 and (progress_info.failed / progress_info.total) > FAILURE_THRESHOLD:
            complete_state = JobState.FAILURE
        _update_job_progress(
            job_id,
            "process",
            progress_info.percentage,
            complete_state=complete_state,
            processed=progress_info.processed,
            remaining=progress_info.remaining,
            failed=progress_info.failed,
        )

        _, t = t(f"TIME: Updated job {job_id} progress in PROCESS stage progress to {progress_info.percentage*100}%")
        job = Job.objects.get(pk=job_id)
        job.logger.info(f"Processing pipeline result for job {job_id}, reply_subject: {reply_subject}")
        job.logger.info(
            f" Job {job_id} progress: {progress_info.processed}/{progress_info.total} images processed "
            f"({progress_info.percentage*100}%), {progress_info.remaining} remaining, {progress_info.failed} failed, "
            f"{len(processed_image_ids)} just processed"
        )
        if error_result:
            job.logger.error(
                f"Pipeline returned error for job {job_id}, image {error_result.image_id}: {error_result.error}"
            )
    except Job.DoesNotExist:
        # don't raise and ack so that we don't retry since the job doesn't exists
        logger.error(f"Job {job_id} not found")
        _ack_task_via_nats(reply_subject, logger)
        return

    acked = False
    try:
        # Save to database (this is the slow operation)
        detections_count, classifications_count, captures_count = 0, 0, 0
        if pipeline_result:
            # should never happen since otherwise we could not be processing results here
            assert job.pipeline is not None, "Job pipeline is None"
            job.pipeline.save_results(results=pipeline_result, job_id=job.pk)
            job.logger.info(f"Successfully saved results for job {job_id}")

            _, t = t(
                f"Saved pipeline results to database with {len(pipeline_result.detections)} detections"
                f", percentage: {progress_info.percentage*100}%"
            )
            # Calculate detection and classification counts from this result
            detections_count = len(pipeline_result.detections)
            classifications_count = sum(len(detection.classifications) for detection in pipeline_result.detections)
            captures_count = len(pipeline_result.source_images)

        # Do NOT ack NATS yet. ACK must happen AFTER the results-stage SREM and
        # _update_job_progress so that a worker crash between save_results and
        # progress commit leaves the message redeliverable. Previously the ACK
        # ran here (before SREM): on crash, NATS drained permanently while
        # Redis pending_images:results kept the id, stranding the job at
        # partial progress with no path to completion. See antenna#1232.
        try:
            progress_info = state_manager.update_state(
                processed_image_ids,
                stage="results",
            )
        except RedisError as e:
            # Transient. save_results dedupes on re-run (get_or_create_detection)
            # and SREM is a no-op on already-removed ids, so a Celery retry is
            # safe for the DB and Redis sets. Counter accumulation is gated on
            # progress_info.newly_removed below, so replays will not inflate
            # detections/classifications/captures (fixes antenna#1232 replay case).
            job.logger.warning(
                f"Transient Redis error updating job {job_id} state (stage=results); Celery will retry: {e}",
                exc_info=True,
            )
            raise

        if not progress_info:
            # State keys genuinely missing (total-images key returned None). Ack
            # first so NATS stops redelivering a message whose state is gone,
            # then fail the job. Mirrors the stage=process missing-state path.
            _ack_task_via_nats(reply_subject, job.logger)
            _fail_job(job_id, "Job state keys not found in Redis (likely cleaned up concurrently)")
            return

        # update complete state based on latest progress info after saving results
        complete_state = JobState.SUCCESS
        if progress_info.total > 0 and (progress_info.failed / progress_info.total) > FAILURE_THRESHOLD:
            complete_state = JobState.FAILURE

        # Counter-inflation guard: only add detection/classification/capture counts
        # when SREM actually removed ids (first processing of this result). On a
        # replay (NATS redelivered the message or the Celery task retried past
        # the SREM), newly_removed==0 and we pass zeros to keep the counters
        # idempotent. The percentage/status path still runs because
        # _update_job_progress uses max() and preserves FAILURE regardless.
        is_first_processing = progress_info.newly_removed > 0
        counts_to_apply = (
            (detections_count, classifications_count, captures_count) if is_first_processing else (0, 0, 0)
        )
        _update_job_progress(
            job_id,
            "results",
            progress_info.percentage,
            complete_state=complete_state,
            detections=counts_to_apply[0],
            classifications=counts_to_apply[1],
            captures=counts_to_apply[2],
        )

        # Ack LAST — only after the results-stage SREM and progress commit are
        # durable. If anything above crashes, NATS will redeliver the message
        # and the full result path re-runs idempotently: save_results dedupes
        # on (detection, source_image), SREM is a no-op on already-removed ids
        # (newly_removed==0 gates counter accumulation), and the progress
        # percentage is clamped by max() to never regress.
        acked = _ack_task_via_nats(reply_subject, job.logger)

    except RedisError:
        # Logged above at the specific update_state call site; re-raise so
        # Celery's autoretry_for handles the transient rather than this broad
        # except swallowing it.
        raise
    except Exception as e:
        error = f"Error processing pipeline result for job {job_id}: {e}"
        if not acked:
            error += ". NATS will re-deliver the task message."

        job.logger.error(error)


def _fail_job(job_id: int, reason: str) -> None:
    from ami.jobs.models import Job, JobState
    from ami.ml.orchestration.jobs import cleanup_async_job_resources

    try:
        with transaction.atomic():
            job = Job.objects.select_for_update().get(pk=job_id)
            if job.status in (JobState.CANCELING, *JobState.final_states()):
                return
            job.update_status(JobState.FAILURE, save=False)
            job.finished_at = datetime.datetime.now()
            job.save(update_fields=["status", "progress", "finished_at"])

        job.logger.error(f"Job {job_id} marked as FAILURE: {reason}")
        cleanup_async_job_resources(job.pk)
    except Job.DoesNotExist:
        logger.error(f"Cannot fail job {job_id}: not found")
        cleanup_async_job_resources(job_id)


def _ack_task_via_nats(reply_subject: str, job_logger: logging.Logger) -> bool:
    """
    Acknowledge a NATS task. Returns True only when JetStream confirmed the ack.

    Callers that gate retry behavior on ack outcome (e.g. the post-save_results
    path in process_nats_pipeline_result) MUST check the return value — a False
    means the message is still live and NATS will redeliver after ack_wait.
    """
    try:

        async def ack_task():
            async with TaskQueueManager() as manager:
                return await manager.acknowledge_task(reply_subject)

        ack_success = async_to_sync(ack_task)()

        if ack_success:
            job_logger.info(f"Successfully acknowledged task via NATS: {reply_subject}")
            return True
        job_logger.warning(f"Failed to acknowledge task via NATS: {reply_subject}")
        return False
    except Exception as ack_error:
        job_logger.error(f"Error acknowledging task via NATS: {ack_error}", exc_info=True)
        return False


def _get_current_counts_from_job_progress(job, stage: str) -> tuple[int, int, int]:
    """
    Get current detections, classifications, and captures counts from job progress.

    Args:
        job: The Job instance
        stage: The stage name to read counts from

    Returns:
        Tuple of (detections, classifications, captures) counts, defaulting to 0 if not found
    """
    try:
        stage_obj = job.progress.get_stage(stage)

        # Initialize defaults
        detections = 0
        classifications = 0
        captures = 0

        # Search through the params list for our count values
        for param in stage_obj.params:
            if param.key == "detections":
                detections = param.value or 0
            elif param.key == "classifications":
                classifications = param.value or 0
            elif param.key == "captures":
                captures = param.value or 0

        return detections, classifications, captures
    except (ValueError, AttributeError):
        # Stage doesn't exist or doesn't have these attributes yet
        return 0, 0, 0


def _update_job_progress(
    job_id: int, stage: str, progress_percentage: float, complete_state: "JobState", **state_params
) -> None:
    from ami.jobs.models import Job, JobState  # avoid circular import

    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job_id)

        # For results stage, accumulate detections/classifications/captures counts
        if stage == "results":
            current_detections, current_classifications, current_captures = _get_current_counts_from_job_progress(
                job, stage
            )

            # Add new counts to existing counts
            new_detections = state_params.get("detections", 0)
            new_classifications = state_params.get("classifications", 0)
            new_captures = state_params.get("captures", 0)

            state_params["detections"] = current_detections + new_detections
            state_params["classifications"] = current_classifications + new_classifications
            state_params["captures"] = current_captures + new_captures

        # Don't overwrite a stage with a stale progress value.
        # This guards against the race where a slower worker calls _update_job_progress
        # after a faster worker has already marked further progress.
        passed_progress = progress_percentage
        existing_progress: float | None = None
        try:
            existing_stage = job.progress.get_stage(stage)
            existing_progress = existing_stage.progress
            progress_percentage = max(existing_stage.progress, progress_percentage)
            # Explicitly preserve FAILURE: once a stage is marked FAILURE it should
            # never regress to a non-failure state, regardless of enum ordering.
            if existing_stage.status == JobState.FAILURE:
                complete_state = JobState.FAILURE
        except (ValueError, AttributeError):
            pass  # Stage doesn't exist yet; proceed normally

        # Diagnostic: when max() lifts the percentage to 1.0 from a partial value
        # this worker computed, surface it. A legitimate jump means another
        # worker concurrently completed the stage; an unexpected jump (e.g. the
        # premature-cleanup pattern described in docs/claude/processing-lifecycle.md
        # as "Bug B") is otherwise invisible.
        if existing_progress is not None and progress_percentage >= 1.0 and passed_progress < 1.0:
            job.logger.warning(
                f"Stage '{stage}' progress lifted to 100% by max() guard: "
                f"this worker passed {passed_progress*100:.1f}%, DB had {existing_progress*100:.1f}%. "
                f"If no other worker just legitimately finished this stage, this is a state-race symptom."
            )

        # Determine the status to write:
        # - Stage complete (100%): use complete_state (SUCCESS or FAILURE)
        # - Stage incomplete but FAILURE already determined: keep FAILURE visible
        # - Stage incomplete, no failure: mark as in-progress (STARTED)
        if progress_percentage >= 1.0:
            status = complete_state
        elif complete_state == JobState.FAILURE:
            status = JobState.FAILURE
        else:
            status = JobState.STARTED

        job.progress.update_stage(
            stage,
            status=status,
            progress=progress_percentage,
            **state_params,
        )
        if job.progress.is_complete():
            job.status = complete_state
            job.progress.summary.status = complete_state
            job.finished_at = datetime.datetime.now()  # Use naive datetime in local time
        job.logger.info(f"Updated job {job_id} progress in stage '{stage}' to {progress_percentage*100}%")
        job.save()

    # Clean up async resources for completed jobs that use NATS/Redis
    if job.progress.is_complete():
        job = Job.objects.get(pk=job_id)  # Re-fetch outside transaction
        # Diagnostic: log which stages satisfied the complete condition. Without
        # this, premature-cleanup bugs (cleanup fires while results are still
        # mid-flight) are hard to trace back to a specific stage transition.
        stages_summary = ", ".join(f"{s.key}={s.progress*100:.1f}% {s.status}" for s in job.progress.stages)
        job.logger.info(f"is_complete()=True after stage='{stage}' update; firing cleanup. Stages: {stages_summary}")
        cleanup_async_job_if_needed(job)


def check_stale_jobs(minutes: int | None = None, dry_run: bool = False) -> list[dict]:
    """
    Find jobs stuck in a running state past the cutoff and revoke them.

    Cutoff is measured against ``Job.updated_at`` (auto-bumped on every save),
    so a job that's actively making progress — including async_api jobs that
    bump on each Redis SREM-driven progress save — is never reaped while
    healthy. Default cutoff is :attr:`Job.STALLED_JOBS_MAX_MINUTES`.

    For each stale job, checks Celery for a terminal task status. REVOKED is
    always trusted. For async_api jobs, SUCCESS and FAILURE are only accepted
    when job.progress.is_complete() — NATS workers may still be delivering
    results after the Celery task finishes. All other cases result in revocation.
    Async resources (NATS/Redis) are cleaned up in both branches.

    Returns a list of dicts describing what was done to each job.
    """
    import datetime

    from celery import states
    from celery.result import AsyncResult
    from django.db import transaction

    from ami.jobs.models import Job, JobDispatchMode, JobState

    if minutes is None:
        minutes = Job.STALLED_JOBS_MAX_MINUTES

    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
    stale_pks = list(
        Job.objects.filter(
            status__in=JobState.running_states(),
            updated_at__lt=cutoff,
        ).values_list("pk", flat=True)
    )

    results = []
    for pk in stale_pks:
        with transaction.atomic():
            try:
                job = Job.objects.select_for_update().get(
                    pk=pk,
                    status__in=JobState.running_states(),
                    updated_at__lt=cutoff,
                )
            except Job.DoesNotExist:
                # Another concurrent run already handled this job.
                continue

            celery_state = None
            if job.task_id:
                try:
                    celery_state = AsyncResult(job.task_id).state
                except Exception:
                    logger.warning(
                        "Failed to fetch Celery state for stale job %s (task_id=%s)",
                        job.pk,
                        job.task_id,
                        exc_info=True,
                    )
                    # Treat as unknown state — job will be revoked below.

            # Only trust terminal Celery states. For async_api jobs, SUCCESS and
            # FAILURE are only accepted when progress is complete — NATS workers may
            # still be delivering results after the Celery task finishes.
            is_terminal = celery_state in states.READY_STATES
            is_async_api = job.dispatch_mode == JobDispatchMode.ASYNC_API
            if is_async_api and celery_state in {states.SUCCESS, states.FAILURE} and not job.progress.is_complete():
                is_terminal = False

            previous_status = job.status
            if is_terminal:
                if not dry_run:
                    job.update_status(celery_state, save=False)
                    job.finished_at = datetime.datetime.now()
                    job.save()
            else:
                # Per-job diagnostic: surface enough state at revoke time that an
                # operator can answer "why was this stalled?" without grepping
                # back through tick logs. Pairs with the per-tick NATS consumer
                # snapshots logged by ``_run_running_job_snapshot_check``.
                stalled_minutes = (datetime.datetime.now() - job.updated_at).total_seconds() / 60
                stages_summary = (
                    ", ".join(f"{s.key}={s.progress*100:.1f}% {s.status}" for s in job.progress.stages)
                    or "(no stages)"
                )
                job.logger.warning(
                    f"Reaping stalled job: no progress for {stalled_minutes:.1f} min "
                    f"(threshold {minutes} min). previous_status={previous_status}, "
                    f"celery_state={celery_state}, dispatch_mode={job.dispatch_mode}, "
                    f"stages: {stages_summary}. "
                    f"For NATS consumer state at the last tick, see prior "
                    f"running_job_snapshots logs for this job."
                )
                if not dry_run:
                    job.update_status(JobState.REVOKED, save=False)
                    job.finished_at = datetime.datetime.now()
                    job.save()

        # Async resource cleanup runs outside the transaction — it makes network
        # calls (NATS/Redis) that should not hold the DB row lock.
        if not dry_run:
            job.refresh_from_db()
            cleanup_async_job_if_needed(job)

        if is_terminal:
            results.append({"job_id": job.pk, "action": "updated", "state": celery_state})
        else:
            results.append({"job_id": job.pk, "action": "revoked", "previous_status": previous_status})

    return results


# Expire queued copies that accumulate while a worker is unavailable so we
# don't process a backlog when a worker reconnects. Kept below the 15-minute
# schedule interval so a backlog is dropped but a single delayed copy still
# runs. Going well below the interval would risk every copy expiring before
# a worker picks it up under moderate broker pressure — change this in lock-
# step with the crontab in migration 0020.
_JOBS_HEALTH_BEAT_EXPIRES = 60 * 14


@dataclasses.dataclass
class JobsHealthCheckResult:
    """Nested result of one :func:`jobs_health_check` tick.

    Each field is the summary for one sub-check and uses the shared
    :class:`IntegrityCheckResult` shape so operators see a uniform
    ``checked / fixed / unfixable`` triple regardless of which check ran.
    Add a new field here when adding a sub-check to the umbrella.
    """

    stale_jobs: IntegrityCheckResult
    running_job_snapshots: IntegrityCheckResult
    zombie_streams: IntegrityCheckResult


def _run_stale_jobs_check() -> IntegrityCheckResult:
    """Reconcile jobs stuck in running states past Job.STALLED_JOBS_MAX_MINUTES."""
    results = check_stale_jobs()
    updated = sum(1 for r in results if r["action"] == "updated")
    revoked = sum(1 for r in results if r["action"] == "revoked")
    logger.info(
        "stale_jobs check: %d stale job(s), %d updated from Celery, %d revoked",
        len(results),
        updated,
        revoked,
    )
    return IntegrityCheckResult(checked=len(results), fixed=updated + revoked, unfixable=0)


def _run_running_job_snapshot_check() -> IntegrityCheckResult:
    """Log a NATS consumer snapshot for each running async_api job.

    Observation-only: ``fixed`` stays 0 because no state is altered. Jobs
    that error during snapshot are counted in ``unfixable`` — a persistently
    stuck job will be picked up on the next tick by ``_run_stale_jobs_check``.
    """
    from ami.jobs.models import Job, JobDispatchMode, JobState

    running_jobs = list(
        Job.objects.filter(
            status__in=JobState.running_states(),
            dispatch_mode=JobDispatchMode.ASYNC_API,
        )
    )
    if not running_jobs:
        return IntegrityCheckResult()

    # Resolve each job's per-job logger synchronously before entering the
    # event loop — ``Job.logger`` attaches a ``JobLogHandler`` on first access
    # which touches the Django ORM, so it is only safe to call from a sync
    # context.
    job_loggers = [(job, job.logger) for job in running_jobs]
    errors = 0

    async def _snapshot_all() -> None:
        nonlocal errors
        # One NATS connection per tick — on a 15-min cadence a per-job fallback
        # is not worth the code. If the shared connection fails to set up, we
        # skip this tick's snapshots and try fresh on the next one.
        async with TaskQueueManager(job_logger=job_loggers[0][1]) as manager:
            for job, job_logger in job_loggers:
                try:
                    # ``log_async`` reads ``job_logger`` fresh each call, so
                    # swapping per iteration routes lifecycle lines to the
                    # right job's UI log.
                    manager.job_logger = job_logger
                    await manager.log_consumer_stats_snapshot(job.pk)
                except Exception:
                    errors += 1
                    logger.exception("Failed to snapshot NATS consumer stats for job %s", job.pk)

    try:
        async_to_sync(_snapshot_all)()
    except Exception:
        # Covers both ``__aenter__`` setup failures (no iteration ran) and the
        # rare ``__aexit__`` teardown failure after a clean loop. In the
        # teardown case this overwrites the per-iteration count with the total
        # — accepted: a persistent failure will show up again next tick.
        logger.exception("Shared-connection snapshot failed; marking tick unfixable")
        errors = len(running_jobs)

    log_fn = logger.warning if errors else logger.info
    log_fn(
        "running_job_snapshots check: %d running async job(s), %d error(s)",
        len(running_jobs),
        errors,
    )
    return IntegrityCheckResult(checked=len(running_jobs), fixed=0, unfixable=errors)


def _run_zombie_streams_check() -> IntegrityCheckResult:
    """Drain NATS streams that outlived their Django Job.

    Defense-in-depth for the cleanup-on-cancel path: a stream whose Job is in
    a terminal state (or was deleted) is consuming worker poll cycles for no
    reason. The age guard (``Job.ZOMBIE_STREAMS_MAX_AGE_MINUTES``) prevents
    races with freshly-dispatched jobs whose NATS stream is created before
    ``transaction.on_commit`` persists the Job row.

    Observations-only for healthy in-flight jobs; only drains when both
    conditions hold:

    * Job is ``None`` or in :meth:`JobState.final_states`
    * Stream's NATS-reported ``created`` timestamp is older than the threshold

    ``checked`` counts job-shaped streams inspected; ``fixed`` counts those
    actually drained; ``unfixable`` counts per-stream drain failures.
    """
    from ami.jobs.models import Job, JobState

    threshold = datetime.timedelta(minutes=Job.ZOMBIE_STREAMS_MAX_AGE_MINUTES)
    now = datetime.datetime.now()

    async def _drain_all() -> tuple[int, int, int]:
        async with TaskQueueManager() as manager:
            snapshots = await manager.list_job_stream_snapshots()
            if not snapshots:
                return 0, 0, 0

            job_ids = [s["job_id"] for s in snapshots]
            jobs_by_id = await sync_to_async(
                lambda ids: {j.pk: j for j in Job.objects.filter(pk__in=ids).only("pk", "status")}
            )(job_ids)

            checked = len(snapshots)
            drained = 0
            errored = 0
            for snap in snapshots:
                created = snap["created"]
                age = now - created if created else threshold + datetime.timedelta(minutes=1)
                if age < threshold:
                    continue
                job = jobs_by_id.get(snap["job_id"])
                job_status = job.status if job else None
                if job is not None and JobState(job_status) not in JobState.final_states():
                    continue
                status_label = str(job_status) if job else "missing"
                try:
                    consumer_deleted = await manager.delete_consumer(snap["job_id"])
                    stream_deleted = await manager.delete_stream(snap["job_id"])
                except Exception:
                    errored += 1
                    logger.exception("Failed draining zombie NATS stream for job %s", snap["job_id"])
                    continue
                if stream_deleted:
                    drained += 1
                    age_hours = age.total_seconds() / 3600.0
                    logger.info(
                        "Drained zombie NATS stream %s (status=%s, age=%.1fh, redelivered=%s, consumer_deleted=%s)",
                        snap["stream_name"],
                        status_label,
                        age_hours,
                        snap["num_redelivered"],
                        consumer_deleted,
                    )
                else:
                    errored += 1
            return checked, drained, errored

    try:
        checked, drained, errored = async_to_sync(_drain_all)()
    except Exception:
        logger.exception("zombie_streams check: connection/setup failed")
        return IntegrityCheckResult(checked=0, fixed=0, unfixable=1)

    log_fn = logger.warning if errored else logger.info
    log_fn(
        "zombie_streams check: %d stream(s) inspected, %d drained, %d error(s)",
        checked,
        drained,
        errored,
    )
    return IntegrityCheckResult(checked=checked, fixed=drained, unfixable=errored)


def _safe_run_sub_check(name: str, fn: Callable[[], IntegrityCheckResult]) -> IntegrityCheckResult:
    """Run one umbrella sub-check, returning an ``unfixable=1`` sentinel on failure.

    The umbrella composes independent sub-checks; one failing must not block
    the others. A raised exception is logged and surfaced as a single
    ``unfixable`` entry so operators watching the task result in Flower see
    the check failed rather than reading zero and assuming all-clear.
    """
    try:
        return fn()
    except Exception:
        logger.exception("%s sub-check failed; continuing umbrella", name)
        return IntegrityCheckResult(checked=0, fixed=0, unfixable=1)


@celery_app.task(soft_time_limit=300, time_limit=360, expires=_JOBS_HEALTH_BEAT_EXPIRES)
def jobs_health_check() -> dict:
    """Umbrella beat task for periodic job-health checks.

    Composes reconciliation (stale jobs) with observation (NATS consumer
    snapshots for running async jobs) so both land in the same 15-minute
    tick — a quietly hung async job gets a snapshot entry right before the
    reconciler decides whether to revoke it. Returns the serialized form of
    :class:`JobsHealthCheckResult` so celery's default JSON backend can store
    it; add new sub-checks by extending that dataclass and calling them here.
    """
    result = JobsHealthCheckResult(
        stale_jobs=_safe_run_sub_check("stale_jobs", _run_stale_jobs_check),
        running_job_snapshots=_safe_run_sub_check("running_job_snapshots", _run_running_job_snapshot_check),
        zombie_streams=_safe_run_sub_check("zombie_streams", _run_zombie_streams_check),
    )
    return dataclasses.asdict(result)


def cleanup_async_job_if_needed(job) -> None:
    """
    Clean up async resources (NATS/Redis) if this job uses them.

    Only jobs with ASYNC_API dispatch mode use NATS/Redis resources.
    This function is safe to call for any job - it checks if cleanup is needed.

    Args:
        job: The Job instance
    """
    from ami.jobs.models import JobDispatchMode

    if job.dispatch_mode == JobDispatchMode.ASYNC_API:
        # import here to avoid circular imports
        from ami.ml.orchestration.jobs import cleanup_async_job_resources

        cleanup_async_job_resources(job.pk)


@task_prerun.connect(sender=run_job)
def pre_update_job_status(sender, task_id, task, **kwargs):
    # in the prerun signal, set the job status to PENDING
    update_job_status(sender, task_id, task, "PENDING", **kwargs)


@task_postrun.connect(sender=run_job)
def update_job_status(sender, task_id, task, state: str, retval=None, **kwargs):
    from ami.jobs.models import Job, JobState

    job_id = task.request.kwargs["job_id"]
    if job_id is None:
        logger.error(f"Job id is None for task {task_id}")
        return
    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        try:
            job = Job.objects.get(task_id=task_id)
        except Job.DoesNotExist:
            logger.error(f"No job found for task {task_id} or job_id {job_id}")
            return

    # Guard only SUCCESS state - let FAILURE, REVOKED, RETRY pass through immediately
    # SUCCESS should only be set when all stages are actually complete
    # This prevents premature SUCCESS when async workers are still processing
    if state == JobState.SUCCESS and not job.progress.is_complete():
        job.logger.info(
            f"Job {job.pk} task completed but stages not finished - " "deferring SUCCESS status to progress handler"
        )
        return

    job.update_status(state)

    # Clean up async resources for revoked jobs
    if state == JobState.REVOKED:
        cleanup_async_job_if_needed(job)


@task_failure.connect(sender=run_job, retry=False)
def update_job_failure(sender, task_id, exception, *args, **kwargs):
    from ami.jobs.models import Job, JobDispatchMode, JobState

    job = Job.objects.get(task_id=task_id)

    # For ASYNC_API jobs where images have been queued to NATS but the final
    # stages have not completed, a run_job failure (e.g. a transient exception
    # raised *after* queue_images_to_nats returned) would otherwise collapse an
    # otherwise-healthy async job: NATS workers are still processing, results
    # are still arriving, but this handler would mark FAILURE and cleanup would
    # destroy the stream/consumer + Redis state mid-flight. Defer terminal
    # state to the async result handler, which owns is_complete() transitions.
    # Mirrors the SUCCESS guard in update_job_status (task_postrun).
    if job.dispatch_mode == JobDispatchMode.ASYNC_API and not job.progress.is_complete():
        job.logger.warning(
            f'Job #{job.pk} "{job.name}" run_job raised but async processing is in-flight; '
            f"deferring FAILURE to async progress handler: {exception}"
        )
        return

    job.update_status(JobState.FAILURE, save=False)

    job.logger.error(f'Job #{job.pk} "{job.name}" failed: {exception}')

    job.save()

    # Clean up async resources for failed jobs
    cleanup_async_job_if_needed(job)


def log_time(start: float = 0, msg: str | None = None) -> tuple[float, Callable]:
    """
    Small helper to measure time between calls.

    Returns: elapsed time since the last call, and a partial function to measure from the current call
    Usage:

    _, tlog = log_time()
    # do something
    _, tlog = tlog("Did something") # will log the time taken by 'something'
    # do something else
    t, tlog = tlog("Did something else") # will log the time taken by 'something else', returned as 't'
    """

    end = time.perf_counter()
    if start == 0:
        dur = 0.0
    else:
        dur = end - start
    if msg and start > 0:
        logger.info(f"{msg}: {dur:.3f}s")
    new_start = time.perf_counter()
    return dur, functools.partial(log_time, new_start)
