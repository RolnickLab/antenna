# Plan: Fix Async Pipeline Job Status Handling

**Date:** 2026-01-30
**Status:** Ready for implementation

## Problem Summary

When `async_pipeline_workers` feature flag is enabled:
1. `queue_images_to_nats()` queues work and returns immediately (lines 400-408 in `ami/jobs/models.py`)
2. The Celery `run_job` task completes without exception
3. The `task_postrun` signal handler (`ami/jobs/tasks.py:175-192`) calls `job.update_status("SUCCESS")`
4. This prematurely marks the job as SUCCESS before async workers actually finish processing

## Solution Overview

Use a **progress-based approach** to determine job completion:
1. Add a generic `is_complete()` method to `JobProgress` that works for any job type
2. In `task_postrun`, only allow SUCCESS if all stages are complete
3. Allow FAILURE, REVOKED, and other terminal states to pass through immediately
4. Authoritative completion for async jobs stays in `_update_job_progress`

---

## Background: Job Types and Stages

Jobs in this app have different types, each with different stages:

| Job Type | Stages |
|----------|--------|
| MLJob | delay (optional), collect, process, results |
| DataStorageSyncJob | data_storage_sync |
| SourceImageCollectionPopulateJob | populate_captures_collection |
| DataExportJob | exporting_data, uploading_snapshot |
| PostProcessingJob | post_processing |

The `is_complete()` method must be generic and work for ALL job types by checking if all stages have finished.

### Celery Signal States

The `task_postrun` signal fires after every task with these states:
- **SUCCESS**: Task completed without exception
- **FAILURE**: Task raised exception (also triggers `task_failure`)
- **RETRY**: Task requested retry
- **REVOKED**: Task cancelled

**Handling strategy:**
| State | Behavior | Rationale |
|-------|----------|-----------|
| SUCCESS | Guard - only set if `is_complete()` | Prevents premature success |
| FAILURE | Allow immediately | Job failed, user needs to know |
| REVOKED | Allow immediately | Job cancelled |
| RETRY | Allow immediately | Transient state |

---

## Implementation Steps

### Step 1: Add `is_complete()` method to JobProgress

**File:** `ami/jobs/models.py` (in the `JobProgress` class, after `reset()` method around line 198)

```python
def is_complete(self) -> bool:
    """
    Check if all stages have finished processing.

    A job is considered complete when ALL of its stages have:
    - progress >= 1.0 (fully processed)
    - status in a final state (SUCCESS, FAILURE, or REVOKED)

    This method works for any job type regardless of which stages it has.
    It's used by the Celery task_postrun signal to determine whether to
    set the job's final SUCCESS status, or defer to async progress handlers.

    Related: Job.update_progress() (lines 924-947) calculates the aggregate
    progress percentage across all stages for display purposes. This method
    is a binary check for completion that considers both progress AND status.

    Returns:
        True if all stages are complete, False otherwise.
        Returns False if job has no stages (shouldn't happen in practice).
    """
    if not self.stages:
        return False
    return all(
        stage.progress >= 1.0 and stage.status in JobState.final_states()
        for stage in self.stages
    )
```

### Step 2: Modify `task_postrun` signal handler

**File:** `ami/jobs/tasks.py` (lines 175-192)

Only guard SUCCESS state - let all other states pass through:

```python
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
            f"Job {job.pk} task completed but stages not finished - "
            "deferring SUCCESS status to progress handler"
        )
        return

    job.update_status(state)
```

### Step 3: Add cleanup to `_update_job_progress`

**File:** `ami/jobs/tasks.py` (lines 151-166)

When job completes, add cleanup for Redis and NATS resources:

```python
def _update_job_progress(job_id: int, stage: str, progress_percentage: float) -> None:
    """
    Update job progress for a specific stage from async pipeline workers.

    This function is called by process_nats_pipeline_result when async workers
    report progress. It updates the job's progress model and, when the job
    completes, sets the final SUCCESS status.

    For async jobs, this is the authoritative place where SUCCESS status
    is set - the Celery task_postrun signal defers to this function.

    Args:
        job_id: The job primary key
        stage: The processing stage (e.g., "process" or "results" for ML jobs)
        progress_percentage: Progress as a float from 0.0 to 1.0
    """
    from ami.jobs.models import Job, JobState  # avoid circular import

    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job_id)
        job.progress.update_stage(
            stage,
            status=JobState.SUCCESS if progress_percentage >= 1.0 else JobState.STARTED,
            progress=progress_percentage,
        )

        # Check if all stages are now complete
        if job.progress.is_complete():
            job.status = JobState.SUCCESS
            job.progress.summary.status = JobState.SUCCESS
            job.finished_at = datetime.datetime.now()  # Use naive datetime in local time
            job.logger.info(f"Job {job_id} completed successfully - all stages finished")

            # Clean up job-specific resources (Redis state, NATS stream/consumer)
            _cleanup_async_job_resources(job_id, job.logger)

        job.logger.info(f"Updated job {job_id} progress in stage '{stage}' to {progress_percentage*100}%")
        job.save()


def _cleanup_async_job_resources(job_id: int, job_logger: logging.Logger) -> None:
    """
    Clean up all async processing resources for a completed job.

    This function is called when an async job completes (all stages finished).
    It cleans up:

    1. Redis state (via TaskStateManager.cleanup):
       - job:{job_id}:pending_images:process - tracks remaining images in process stage
       - job:{job_id}:pending_images:results - tracks remaining images in results stage
       - job:{job_id}:pending_images_total - total image count for progress calculation

    2. NATS JetStream resources (via TaskQueueManager.cleanup_job_resources):
       - Stream: job_{job_id} - the message stream that holds pending tasks
       - Consumer: job-{job_id}-consumer - the durable consumer that tracks delivery

    Why cleanup is needed:
    - Redis keys have a 7-day TTL but should be cleaned immediately when job completes
    - NATS streams/consumers have 24-hour retention but consume server resources
    - Cleaning up immediately prevents resource accumulation from many jobs

    Cleanup failures are logged but don't fail the job - data is already saved.

    Args:
        job_id: The job primary key
        job_logger: Logger instance for this job (writes to job's log file)
    """
    # Cleanup Redis state tracking
    state_manager = TaskStateManager(job_id)
    state_manager.cleanup()
    job_logger.info(f"Cleaned up Redis state for job {job_id}")

    # Cleanup NATS resources (stream and consumer)
    try:
        async def cleanup_nats():
            async with TaskQueueManager() as manager:
                return await manager.cleanup_job_resources(job_id)

        success = async_to_sync(cleanup_nats)()
        if success:
            job_logger.info(f"Cleaned up NATS resources for job {job_id}")
        else:
            job_logger.warning(f"Failed to clean up NATS resources for job {job_id}")
    except Exception as e:
        job_logger.error(f"Error cleaning up NATS resources for job {job_id}: {e}")
        # Don't fail the job if cleanup fails - job data is already saved
```

### Step 4: Verify existing error handling

**File:** `ami/jobs/models.py` (lines 402-408)

**No changes needed** - Existing code already handles FAILURE correctly:
```python
if not queued:
    job.logger.error("Aborting job %s because images could not be queued to NATS", job.pk)
    job.progress.update_stage("collect", status=JobState.FAILURE)
    job.update_status(JobState.FAILURE)
    job.finished_at = datetime.datetime.now()
    job.save()
    return
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `ami/jobs/models.py` | ~198 (in JobProgress class) | Add generic `is_complete()` method |
| `ami/jobs/models.py` | ~700 (Job class docstring) | Add future improvements note |
| `ami/jobs/tasks.py` | 175-192 | Guard SUCCESS with `is_complete()` check |
| `ami/jobs/tasks.py` | 151-166 | Use `is_complete()`, add cleanup with docstring |
| `ami/jobs/tasks.py` | imports | Add import for `TaskStateManager` |

**Related existing code (not modified):**
- `Job.update_progress()` at lines 924-947 - calculates aggregate progress from stages

---

## Why This Approach Works

| Job Type | Stages Complete When Task Ends? | `task_postrun` Behavior |
|----------|--------------------------------|------------------------|
| Sync ML job | Yes - all stages marked SUCCESS | Sets SUCCESS normally |
| Async ML job | No - stages incomplete | Skips SUCCESS, defers to async handler |
| DataStorageSyncJob | Yes - single stage | Sets SUCCESS normally |
| DataExportJob | Yes - all stages | Sets SUCCESS normally |
| Any job that fails | N/A | FAILURE passes through |
| Cancelled job | N/A | REVOKED passes through |

---

## Race Condition Analysis: `update_progress()` vs `is_complete()`

### How `update_progress()` works (lines 924-947)

Called automatically by `save()` (line 958-959), it auto-corrects stage status/progress:

```python
for stage in self.progress.stages:
    if stage.progress > 0 and stage.status == JobState.CREATED:
        stage.status = JobState.STARTED  # Auto-upgrade CREATED→STARTED
    elif stage.status in JobState.final_states() and stage.progress < 1:
        stage.progress = 1  # If final, ensure progress=1
    elif stage.progress == 1 and stage.status not in JobState.final_states():
        stage.status = JobState.SUCCESS  # Auto-upgrade to SUCCESS if progress=1
```

**Key insight:** Line 939-941 auto-sets SUCCESS only if `progress == 1`. For async jobs, incomplete stages have `progress < 1`, so they won't be auto-upgraded.

### When is `is_complete()` called?

1. **In `task_postrun`:** Job loaded fresh from DB (already saved by `job.run()`)
2. **In `_update_job_progress`:** After `update_stage()` but before `save()`

### Async job flow - no race condition:

```
run_job task:
1. job.run() → MLJob.run()
2. collect stage set to SUCCESS, progress=1.0
3. job.save() called → update_progress() runs → no changes (only collect is 100%)
4. queue_images_to_nats() called, returns
5. job.run() returns successfully

task_postrun fires:
6. job = Job.objects.get(pk=job_id)  # Fresh from DB
7. Job state: collect=SUCCESS(1.0), process=CREATED(0), results=CREATED(0)
8. is_complete() → False (not all stages at 100% final)
9. SUCCESS status deferred ✓

Async workers process images:
10. process_nats_pipeline_result called for each result
11. _update_job_progress("process", 0.5) → is_complete() = False
12. _update_job_progress("process", 1.0) → is_complete() = False (results still 0)
13. _update_job_progress("results", 0.5) → is_complete() = False
14. _update_job_progress("results", 1.0) → is_complete() = True ✓
15. Job marked SUCCESS, cleanup runs
```

### Why there's no race:

1. `is_complete()` requires ALL stages to have `progress >= 1.0` AND `status in final_states()`
2. For async jobs, incomplete stages have `progress < 1.0`, so `update_progress()` won't auto-upgrade them
3. The async handler updates stages separately (process, then results), so completion only triggers when the LAST stage reaches 100%
4. `select_for_update()` in `_update_job_progress` prevents concurrent updates to the same job

---

## Risk Analysis

**Core work functions that must NOT be affected:**
1. `queue_images_to_nats()` - queues images to NATS for async processing
2. `process_nats_pipeline_result()` - processes results from async workers
3. `pipeline.save_results()` - saves detections/classifications to database
4. `MLJob.process_images()` - synchronous image processing path

**Changes and their risk:**

| Change | Risk to Core Work | Analysis |
|--------|------------------|----------|
| Add `is_complete()` to JobProgress | **None** | Pure read-only check, doesn't modify any state |
| Guard SUCCESS in `task_postrun` | **None** | Only affects status display, not actual processing. Returns early without modifying anything. |
| Use `is_complete()` in `_update_job_progress` | **None** | Replaces hardcoded `stage == "results" and progress >= 1.0` check with generic method. Called AFTER `pipeline.save_results()` completes. |
| Add `_cleanup_async_job_resources()` | **Minimal** | Called ONLY after job is marked SUCCESS. Cleanup failures are caught and logged, don't fail the job. Data is already saved at this point. |

**Worst case scenario:** If `is_complete()` has a bug and always returns False:
- Work still completes normally (queuing, processing, saving all happen)
- Job status would stay STARTED instead of SUCCESS
- UI would show job as incomplete even though work finished
- **Data is safe** - this is a display/status issue, not a data loss risk

**Existing function to note:** `Job.update_progress()` at lines 924-947 calculates total progress from stages. The new `is_complete()` method is a related concept - checking if all stages are done vs calculating aggregate progress.

---

## Future Improvements (out of scope)

Per user feedback, consider for follow-up:
- Split job types into different classes with clearer state management
- More robust state machine for job lifecycle
- But don't reinvent state tracking on top of existing bg task tools

These improvements should be noted in the Job class docstring.

---

## Additional Documentation

### Add note to Job class docstring

**File:** `ami/jobs/models.py` (Job class, around line ~700)

Add to the class docstring:
```python
# Future improvements:
# - Consider splitting job types into subclasses with clearer state management
# - The progress/stages system (see JobProgress, update_progress()) was designed
#   for UI display. The is_complete() method bridges this to actual completion logic.
# - Avoid reinventing state tracking on top of existing background task tools
```

---

## Verification

1. **Unit test for `is_complete()`:**
   - No stages -> False
   - One stage at progress=0.5, STARTED -> False
   - One stage at progress=1.0, STARTED -> False (not final state)
   - One stage at progress=1.0, SUCCESS -> True
   - Multiple stages, all SUCCESS -> True
   - Multiple stages, one still STARTED -> False

2. **Unit test for task_postrun behavior:**
   - SUCCESS with incomplete stages -> status NOT changed
   - SUCCESS with complete stages -> status changed to SUCCESS
   - FAILURE -> passes through immediately
   - REVOKED -> passes through immediately

3. **Integration test for async ML job:**
   - Create job with async_pipeline_workers enabled
   - Queue images to NATS
   - Verify job status stays STARTED after run_job completes
   - Process all images via process_nats_pipeline_result
   - Verify job status becomes SUCCESS after all stages finish
   - Verify finished_at is set
   - Verify Redis/NATS cleanup occurred

4. **Regression test for sync jobs:**
   - Run sync ML job -> SUCCESS after task completes
   - Run DataStorageSyncJob -> SUCCESS after task completes
   - Run DataExportJob -> SUCCESS after task completes
