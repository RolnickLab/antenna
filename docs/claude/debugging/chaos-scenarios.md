# Chaos scenarios for async_api jobs

Manual fault-injection runbook for validating the `process_nats_pipeline_result`
retry path, the ACK/SREM ordering, and the terminal-vs-transient Redis error
boundary. Unit tests in `ami/jobs/tests/test_tasks.py` cover the task body, but
they do not exercise `autoretry_for`, real Celery backoff, or NATS redelivery —
this runbook does.

Run against a live local stack. Do not run against production.

## Prereqs

- `docker compose ps` — all services healthy (django, celeryworker, redis, nats, rabbitmq).
- ADC worker running a pipeline registered on the target project. Current
  verified combo: project 20, pipeline `mothbot_insect_orders_2025`.
- A fresh `SourceImageCollection` with enough images that process stage takes
  >10s — otherwise there's no window to inject the fault mid-flight.
- `git status` clean. Fault-injection patches must be reverted before commit.

## Fault-injection primitives

### 1. `chaos_monkey` management command

Wipes runtime state:

```
docker compose exec django python manage.py chaos_monkey flush redis
docker compose exec django python manage.py chaos_monkey flush nats
```

- `flush redis` → FLUSHDB on the default db. Every in-flight `update_state`
  call will see `total_raw=None` and return `None` from that point on → the
  caller takes the terminal "keys genuinely gone" path (ACK + `_fail_job`).
- `flush nats` → deletes every JetStream stream. Workers mid-pull see
  `NotFoundError`. Existing Redis state is untouched.

### 2. One-shot transient RedisError via sentinel file

To simulate a connection reset or timeout without actually killing Redis:

1. Patch `AsyncJobStateManager.update_state` at the top of the method body:

   ```python
   import os
   if os.path.exists("/tmp/inject-redis-fault"):
       os.remove("/tmp/inject-redis-fault")
       raise RedisError("injected transient fault")
   ```

2. Arm: `docker compose exec celeryworker touch /tmp/inject-redis-fault`.
3. The file auto-removes on the first task hit, so exactly one invocation
   sees the fault; Celery's `autoretry_for=(RedisError, ...)` retries and the
   retry succeeds.
4. **Revert the patch and restart celeryworker** before committing.

Do NOT use `redis-cli CLIENT KILL TYPE normal` for this — django-redis's
connection pool transparently reconnects and the error never reaches the
caller.

## Scenarios

Run these in order. Each one verifies a distinct path in Fix 1's reordered
ACK/SREM code.

### Scenario A: happy path

Baseline. Confirms the lifecycle doc's Section 1 matches reality.

1. Dispatch a job:
   ```
   docker compose exec -T django python manage.py test_ml_job_e2e \
     --project 20 --collection <id> --pipeline <slug> --dispatch-mode async_api
   ```
2. Watch logs:
   ```
   docker compose logs celeryworker --since 10s --follow 2>&1 | \
     grep --line-buffered -E \
     "Pending images from Redis|Updated job .* progress|Finalizing NATS consumer|ERROR|FAILURE"
   ```
3. Expected: all stages hit 100% SUCCESS; `Finalizing NATS consumer` appears
   exactly once per worker; no ERROR or FAILURE lines.

### Scenario B: transient RedisError mid-flight (ack_wait holds the message)

Verifies `autoretry_for` is what retries — not a Celery swallowing the error.

1. Patch `update_state` with the sentinel-file block above.
2. Restart celeryworker: `docker compose restart celeryworker`.
3. Dispatch a job, wait for process stage to pass 10%.
4. Arm: `docker compose exec celeryworker touch /tmp/inject-redis-fault`.
5. Expected in logs:
   - One `Transient Redis error updating job ... state (stage=...)` warning.
   - Celery `retry: Retry in N.Ns` line.
   - Next invocation succeeds; stage progress resumes.
   - NO `Job state keys not found in Redis` (that is the terminal path).
6. Job completes SUCCESS.
7. Revert the patch; `docker compose restart celeryworker`; `git diff` clean.

### Scenario C: genuine Redis state loss (FLUSHDB mid-flight)

Verifies the terminal path: update_state returns None → ACK → `_fail_job`.

1. Dispatch a job, wait for process stage >10%.
2. `docker compose exec django python manage.py chaos_monkey flush redis`.
3. Expected in logs:
   - `Pending images from Redis for job X ...` stops emitting for this job.
   - `Job state keys not found in Redis (likely cleaned up concurrently)`
     appears.
   - `Changing status of job <id>` to FAILURE.
   - NATS consumer finalized once (not per-worker — the remaining workers
     see no state to reconcile).
4. Job row: `status=FAILURE`, finished_at set.

### Scenario D: ACK/SREM ordering (Bug A crash window)

Verifies Fix 1's reorder: a crash anywhere between save_results and the
ACK leaves the NATS message redeliverable. This scenario drops the
crash point at the narrowest window — between the results-stage SREM
(`state_manager.update_state(stage="results")`) and `_ack_task_via_nats`
— because that is the window that stranded jobs on pre-Fix-1 code.

1. Patch `process_nats_pipeline_result` to `os._exit(1)` between
   `state_manager.update_state(stage="results")` and `_ack_task_via_nats(...)`.
   (Pick a deterministic trigger — e.g., check for `/tmp/crash-after-srem`.)
2. Restart celeryworker.
3. Dispatch a job. Arm with `touch /tmp/crash-after-srem`.
4. Expected:
   - First worker to hit the trigger dies without ACKing.
   - NATS `ack_wait` (30s) elapses.
   - Message redelivered to another worker.
   - save_results dedupes, SREM is a no-op (`newly_removed=0`),
     counter accumulation skipped.
   - Job eventually completes SUCCESS; counters match image count exactly.
5. On pre-Fix-1 code, this scenario strands the image: ACK fires before the
   planned crash point, so NATS has no record to redeliver; Redis keeps the
   id in `pending_images:results` forever.
6. Revert the patch; restart; `git diff` clean.

### Scenario E: Celery retries exhausted (max_retries=5)

Verifies the job flips to FAILURE cleanly after budget exhaustion, not
stranded at partial progress.

1. Patch `update_state` to unconditionally raise `RedisError("persistent")`.
2. Restart celeryworker.
3. Dispatch a job.
4. Expected:
   - 5× `Transient Redis error` warnings with exponential backoff
     (1s, 2s, 4s, 8s, 15s capped by `retry_backoff_max`).
   - `MaxRetriesExceededError` in Celery logs.
   - `task_failure` signal fires, but the Bug C guard defers: the job stays
     STARTED because `progress.is_complete()` is False and dispatch_mode
     is ASYNC_API. A stale-job reaper (Fix 2, out of scope here) would
     eventually revoke it.
5. Revert; restart; `git diff` clean.

### Scenario F: max_deliver exhaustion → reconciler marks images failed

Verifies the `mark_lost_images_failed` sub-check inside `jobs_health_check`:
when NATS has given up redelivering messages (hit `max_deliver`) but Redis
still tracks them as pending, the reconciler marks them failed so the job
lands in SUCCESS/FAILURE instead of being REVOKEd by the stale-job reaper
(which would nuke legitimate processed work).

No code patches required — the chaos is driven entirely by a management
command.

1. Pick a fake job id (e.g. `999999`) and fake image ids (`img-a,img-b,img-c`).
2. Seed Redis pending sets:
   ```
   docker compose exec django python manage.py shell -c "
   from ami.ml.orchestration.async_job_state import AsyncJobStateManager
   AsyncJobStateManager(999999).initialize_job(['img-a', 'img-b', 'img-c'])
   "
   ```
3. Create a minimal Job row with `dispatch_mode=ASYNC_API` and back-date
   `updated_at` past `STALLED_JOBS_MAX_MINUTES`.
4. Drive the NATS consumer past `max_deliver` without ADC:
   ```
   docker compose exec django python manage.py chaos_monkey exhaust_max_deliver \
     --job-id 999999 --image-ids img-a,img-b,img-c --ensure-stream
   ```
   Takes ~66s (`NATS_MAX_DELIVER × (TASK_TTR + 3s)` + final settle). Prints
   `num_pending=0 num_ack_pending=3 num_redelivered=3` on exit.
5. Invoke the reconciler:
   ```
   docker compose exec django python manage.py shell -c "
   from ami.jobs.tasks import mark_lost_images_failed
   print(mark_lost_images_failed())
   "
   ```
6. Expected:
   - Reconciler returns `[{'job_id': 999999, 'action': 'marked_failed', 'lost_count': 3}]`.
   - Job row flips to `FAILURE` (3/3 = 100% > `FAILURE_THRESHOLD`). With a
     realistic ratio (e.g. 6 lost out of 20, <50%), it would flip to `SUCCESS`.
   - `job.progress.errors` has a line starting with `jobs_health_check: marked N image(s) as failed (job idle past cutoff; ...)`.
   - `cleanup_async_job_if_needed` fires on completion; NATS stream + Redis
     keys deleted.
7. Cleanup: `Job.objects.filter(pk=999999).delete()` (stream/Redis already
   drained by the reconciler's cleanup trigger).

## Gotchas

- **celeryworker startup noise**: first ~60s after restart, the
  `check_processing_services_online` beat task monopolises
  `ForkPoolWorker-16` retrying unreachable services. Wait for that to settle
  before dispatching.
- **RabbitMQ stale connection**: if Django has been up >1 day, AMQP
  connections go stale → `ConnectionResetError: [Errno 104]`. Fix:
  `docker compose restart django` before dispatching.
- **Volume mount**: `ami/` is live-mounted. Patches take effect only after
  `docker compose restart celeryworker`.
- **Uncommitted patch leak**: always `git diff` before committing. The
  sentinel-file pattern is disruptive; losing the revert turns every
  subsequent test into a fault-injection run.
