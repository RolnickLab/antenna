# ASYNC_API job processing lifecycle

Covers `dispatch_mode=ASYNC_API` only. Sync/Celery-only dispatch has a different
shape and isn't documented here.

This doc exists so the next triage session can answer *"where would this
hang?"* without re-deriving the architecture from `models.py` →
`tasks.py` → `orchestration/*.py` → `nats_queue.py`. Read Section 2 first
when triaging a stuck job — the invariants table points at the class of bug.

## 1. Happy-path flow

```
[user] POST /api/v2/jobs/{id}/run?start_now=true
  └─> Job.enqueue()                                                 ami/jobs/models.py:904
      └─> run_job.apply_async(...)                         [Celery task enqueued]

[celeryworker] run_job(job_id)                                      ami/jobs/tasks.py:30
  └─> MLJob.run(job)                                                ami/jobs/models.py:432
      ├─> collect: STARTED → 0                       Job.progress.stages[collect]
      ├─> pipeline.collect_images(...)               [iterable resolved]
      ├─> collect: SUCCESS → 1.0                     Job.progress.stages[collect]
      └─> queue_images_to_nats(job, images)                         ami/ml/orchestration/jobs.py:75
          ├─> AsyncJobStateManager.initialize_job(image_ids)        ami/ml/orchestration/async_job_state.py:85
          │     [Redis: SET job:X:pending_images_total N             ex=7d]
          │     [Redis: SADD job:X:pending_images:process  *ids      ex=7d]
          │     [Redis: SADD job:X:pending_images:results  *ids      ex=7d]
          └─> TaskQueueManager.publish_task(...) × N                 ami/ml/orchestration/nats_queue.py:359
                [NATS: stream ami-jobs-X, consumer job-X-consumer, N messages]

  [run_job returns — Celery task_postrun fires]
  └─> update_job_status(state=SUCCESS)                              ami/jobs/tasks.py:627
      └─> guard: progress.is_complete() == False (process/results @ 0%)
          → defers SUCCESS transition to the async progress handler

[adc/gpu worker] pulls NATS message
  └─> processes image, POSTs to /api/v2/jobs/{id}/result
      └─> endpoint queues process_nats_pipeline_result(job_id, result_data, reply_subject)

[celeryworker] process_nats_pipeline_result(...)                    ami/jobs/tasks.py:76
  ├─> state_manager.update_state(stage="process", ids)              [Redis: SREM pending:process]
  ├─> _update_job_progress("process", percentage, ...)              [Job.progress.stages[process]]
  ├─> pipeline.save_results(results, job_id)                        [DB: Detections + Classifications]
  ├─> state_manager.update_state(stage="results", ids)              [Redis: SREM pending:results]
  ├─> _update_job_progress("results", percentage, ...)              [Job.progress.stages[results]]
  │     └─> if job.progress.is_complete():
  │         └─> cleanup_async_job_if_needed(job)                    ami/jobs/tasks.py:657
  │             └─> AsyncJobStateManager.cleanup()                  [Redis: DEL job:X:*]
  │             └─> TaskQueueManager.cleanup_job_resources(...)     [NATS: del consumer, del stream]
  └─> _ack_task_via_nats(reply_subject)                             ami/jobs/tasks.py:255
```

**Why ACK runs last:** the results-stage SREM and `_update_job_progress`
must be durable in Redis and Postgres before NATS is told the message is
done. If a worker crashes anywhere above the ACK, NATS does not see an
ack within `ack_wait` (30s) and redelivers. The replay re-enters the
same code path idempotently:

- `save_results` dedupes on `(detection, source_image)`.
- SREM is a no-op on already-removed IDs; the `newly_removed` return
  (SREM's integer result) is 0, which gates counter accumulation so
  detections/classifications/captures do not inflate.
- `_update_job_progress` clamps the percentage with `max()` so progress
  never regresses, and preserves FAILURE once set.

Earlier revisions of this code ACKed *before* the results-stage SREM. A
worker crash between those two lines left NATS drained (message already
acked, no redelivery) while Redis `pending_images:results` permanently
held that image ID — the job would never reach 100% on the results stage,
and no code path reconciled it.

## 2. State invariants

At any moment during a healthy async_api job, these must hold. One-line
checks for each — run them against a job_id that's suspected stuck.

| Invariant | One-line check |
|---|---|
| If `Job.status==STARTED` and async_api, either NATS has work (num_pending+num_ack_pending>0) or Redis is empty + progress is 100% | `redis-cli -n 1 SCARD job:{id}:pending_images:results`; then see §5 for the NATS half |
| `Redis SCARD pending:results` ≤ `NATS delivered - ack_floor` at rest | if SCARD>0 but NATS shows everything acked, that's the pre-PR-#1234 Bug A signature — should not happen against current code |
| `job.progress.stages` contains `collect`, `process`, `results` before `run_job` exits | stages are initialized in `Job.setup()`, not lazily — see `ami/jobs/models.py:944-955` |
| Cleanup only fires when `Job.status in final_states` OR `progress.is_complete() == True` | grep log for `Finalizing NATS consumer` — timestamp must be ≥ all `_update_job_progress` timestamps |
| `is_complete()` returns True iff every stage has `progress>=1.0 AND status in final_states` | `ami/jobs/models.py:245-267` — works off an exhaustive stage list |
| `_update_job_progress` counter-accumulator on `results` stage runs *only when this batch's SREM newly removed IDs* | gated on `progress_info.newly_removed` (SREM's integer return) at `ami/jobs/tasks.py:228`. Pre-Fix-1 revisions inflated on replay (antenna#1232). |

If any invariant is violated, the failure mode is probably below.

## 3. Failure modes

| Symptom | Likely cause | Diagnostic | Fix direction |
|---|---|---|---|
| Job STARTED forever; NATS drained; Redis `pending:results` > 0 | Worker crashed between ACK and results-stage SREM (Bug A) | `redis-cli -n 1 SCARD job:{id}:pending_images:results` > 0 AND NATS `num_pending+num_ack_pending == 0` | Addressed by PR #1234 (ACK now runs after the results SREM + progress commit; crashes leave the message redeliverable). The 15-min stale-job reaper is the safety net if this class of bug resurfaces. |
| Job stuck at <100% indefinitely; most images processed; Redis `pending:process` or `pending:results` has a small remainder; NATS consumer shows `num_redelivered > 0` | NATS gave up redelivering after `max_deliver=2` (the 2 delivery attempts both failed non-retriably — the payload, handler, or DB side). Empirically, JetStream keeps those messages in `num_ack_pending` indefinitely rather than clearing them. | `redis-cli -n 1 SMEMBERS job:{id}:pending_images:process` has ids AND `updated_at` is >10 min old AND last `Pending images from Redis` log line was >10 min ago | Addressed by `mark_lost_images_failed` (PR #1244) — new sub-check inside `jobs_health_check` that runs BEFORE `check_stale_jobs`, marks the still-pending ids as failed and pushes progress to 100% so the existing completion logic lands the job in SUCCESS or FAILURE based on `FAILURE_THRESHOLD`. Preserves legitimate processed work instead of REVOKE-nuking the whole job. |
| Job FAILURE within 30-60s of dispatch; cleanup fired mid-processing | Premature `cleanup_async_job_resources` — `is_complete()` momentarily True (Bug B, not yet reproduced) | grep log `Finalizing NATS consumer` for job, compare timestamp to `Finished job` (run_job exit) and first `Updated job ... progress` line | Separate issue (see drafts in ami-devops). Not in scope for Fix 1. |
| Transient `run_job` exception flips job to FAILURE even though 100+ images were successfully queued | `task_failure` signal missing ASYNC_API guard (Bug C) | grep log for `task_failure` on `run_job` + Job row status=FAILURE + Redis still has pending IDs | Guarded in `update_job_failure` at `tasks.py:729`: defers FAILURE for ASYNC_API jobs when `progress.is_complete()` is False, mirroring the `task_postrun` SUCCESS guard. Stale-job reaper eventually revokes if the job truly stays stuck. |
| `Job state keys not found in Redis` log line | Either genuine cleanup race, or transient Redis error being misreported | If paired with autoretry-backoff log lines, it's transient (normal); if one-shot, check if cleanup fired earlier for this job_id | Already fixed in #1219/#1231 (transient path now autoretries + logs distinctly) |
| Batch processing crashes with OOM on the GPU worker | DataLoader leak (unrelated to antenna) | `dmesg -T \| grep -i oom` on ADC host | Mitigated with `AMI_NUM_WORKERS=1` in ADC config |
| Broker "Connection reset by peer" hourly on celeryworker | TCP keepalive not applied in deployment | `cat /proc/sys/net/ipv4/tcp_keepalive_time` in the container | `apply_keepalive_fix.sh` in ami-devops |
| 15-min `NATS consumer status` log lines stop appearing mid-job | Consumer was deleted (cleanup already fired); snapshot silently no-ops on missing consumer | grep log for `Deleted NATS consumer` before the gap | Symptom of Bug A or Bug B above — find the root cause |

## 4. Call-site reference

Non-obvious places that touch lifecycle state. File:line shown; don't quote code.

**Cleanup triggers — when and what state it sees:**
- `_update_job_progress` at `ami/jobs/tasks.py:432` — fires `cleanup_async_job_if_needed(job)` when `is_complete()` returns True. Runs after the DB transaction commits. State seen: final stage progress in Job.progress. Bug B would be here if `is_complete()` returns True on a transient view of the stages.
- `update_job_status` (task_postrun) at `ami/jobs/tasks.py:683` — fires cleanup only on `state == REVOKED`. SUCCESS is deferred via the `is_complete()` guard at line 702.
- `update_job_failure` (task_failure) at `ami/jobs/tasks.py:715` — for ASYNC_API jobs, defers FAILURE + cleanup when `progress.is_complete()` is False (the Bug C guard at line 729). For other dispatch modes, and for ASYNC_API jobs that have actually finished, still marks FAILURE and fires cleanup. The stale-job reaper is the safety net if the deferred path never converges.
- `check_stale_jobs` at `ami/jobs/tasks.py:435` — fires cleanup on every stale job after `FAILED_CUTOFF_HOURS=72` whether it was marked REVOKED or updated-from-celery.
- `_fail_job` at `ami/jobs/tasks.py:270` — fires cleanup after marking job FAILURE.
- `MLJob.run` at `ami/jobs/models.py:488` — fires cleanup on the zero-images path when is_complete is true immediately after `queue_images_to_nats`.

**`_fail_job` call sites — when the terminal path is taken:**
- `process_nats_pipeline_result` at `tasks.py:132` — Redis `update_state` for process returned None (keys genuinely missing).
- `process_nats_pipeline_result` at `tasks.py:214` — same but for results stage.

**`_update_job_progress` — stage params and accumulator:**
- `tasks.py:359` — `results` stage branch accumulates detections/classifications/captures by READING current Job.progress and ADDING. The caller gates this accumulation on `progress_info.newly_removed > 0` (see `tasks.py:228`) so replays pass zero counts and leave the totals idempotent.
- `max()` guard at `tasks.py:381` — prevents progress regression when a slower worker lands after a faster one.

**`is_complete()` — single source of truth at `models.py:245-267`:**
- Returns False if `self.stages` is empty (sanity check).
- Returns True only when EVERY stage has `progress>=1.0 AND status in final_states()`.
- `Job.setup()` at `models.py:923` initializes the full stage list before the run, so `is_complete()` at runtime sees an exhaustive list (not a partial one). This is what makes Bug B puzzling — the obvious "lazy stage" hypothesis doesn't fit.

**`state_manager.update_state` — Redis pipeline structure at `async_job_state.py:112`:**
- Always returns a `JobStateProgress` dataclass or `None`.
- `None` means the total-images key is gone (job expired, cleaned up concurrently, or never initialized). This is a terminal signal.
- Raises `RedisError` on transient (connection reset, timeout). Callers must let autoretry_for handle this — swallowing it conflates transient with terminal (see #1219).
- Returns `newly_removed` on `JobStateProgress` (SREM's integer return at `async_job_state.py:163`) so `process_nats_pipeline_result` can gate counter accumulation on the results stage.

**`state_manager.cleanup` at `async_job_state.py:215` — idempotent:**
- `DEL` on a non-existent key is a no-op. Safe to call multiple times for the same job.

## 5. Full trace for a single job

Copy-paste block. Replace `JOB_ID` and run inside the django container (or
swap `docker compose exec` for your deployment's equivalent).

```bash
JOB_ID=2411

# Job row state (status, progress, stages, task_id, timestamps)
docker compose exec django python manage.py shell -c "
from ami.jobs.models import Job
import json
j = Job.objects.get(pk=$JOB_ID)
print(f'status={j.status} task_id={j.task_id} dispatch={j.dispatch_mode}')
print(f'started_at={j.started_at} finished_at={j.finished_at} updated_at={j.updated_at}')
print(f'progress.summary={j.progress.summary}')
for s in j.progress.stages:
    print(f'  stage={s.key} progress={s.progress:.2%} status={s.status}')
print('errors:', j.progress.errors[-3:] if j.progress.errors else [])
"

# Redis state for this job
docker compose exec redis redis-cli -n 1 keys "job:$JOB_ID:*"
docker compose exec redis redis-cli -n 1 get "job:$JOB_ID:pending_images_total"
docker compose exec redis redis-cli -n 1 scard "job:$JOB_ID:pending_images:process"
docker compose exec redis redis-cli -n 1 scard "job:$JOB_ID:pending_images:results"
docker compose exec redis redis-cli -n 1 scard "job:$JOB_ID:failed_images"

# NATS stream + consumer state (reads through the antenna client for auth/URL)
docker compose exec django python manage.py shell -c "
from ami.ml.orchestration.nats_queue import TaskQueueManager
from asgiref.sync import async_to_sync
async def _():
    async with TaskQueueManager() as m:
        await m.log_consumer_stats_snapshot($JOB_ID)
async_to_sync(_)()
" 2>&1 | tail -5

# Last 50 log lines referencing this job
docker compose logs celeryworker --tail=2000 2>&1 | grep -E "job[^a-z]+$JOB_ID|'$JOB_ID'|#$JOB_ID" | tail -50
```

**Reading the output:**
- If `status=STARTED` and both SCARDs are 0 → job should be marked done. If NATS is also drained, the 15-min snapshot will notice but won't transition (Fix 2 territory).
- If `status=STARTED` and `pending_images:results > 0` but NATS shows `num_pending=0 num_ack_pending=0` → Bug A. Redis holds image IDs that NATS already acked. Stuck.
- If `status=FAILURE` and `finished_at - started_at < 60s` on a job with >50 images → Bug B (premature cleanup) or Bug C (task_failure without guard). Compare `Finalizing NATS consumer` timestamp to the dispatch timestamp to tell which.

---

Last updated: 2026-04-15. Reflects PR #1234 (ACK runs after results-stage
SREM + progress commit; `task_failure` guard for in-flight ASYNC_API jobs;
counter accumulation gated on `newly_removed`).
