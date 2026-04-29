# Plan: reaper checks Redis directly via `all_tasks_processed()` (fix/job-complete-check)

## Why

Production job 2521 (project 192, ~4510 images, async_api) finished with all
4510 NATS messages acked and Redis pending sets empty, but `Job.progress`
JSONB had `process=99.98% STARTED processed=4509 remaining=1`. The
`jobs_health_check` reaper at the 10-min cutoff:

1. `mark_lost_images_failed` correctly skipped the job (Redis pending was
   empty, so `lost_ids` was empty — the documented skip path).
2. `check_stale_jobs` found Celery `state=SUCCESS` but the async_api guard
   at `ami/jobs/tasks.py:968` consults `job.progress.is_complete()`, which
   returned False because of the clobbered `process` stage.
3. Reaper REVOKEd the job. 5058 detections / 8129 classifications already
   saved to DB; Job row reads REVOKED.

PR #1244's reconciler is the wrong tool for this symptom — there is nothing
to reconcile in Redis. The bug is upstream: `_update_job_progress`
(`tasks.py:556`) writes the entire `progress` JSONB blob without a row
lock (PR #1261 dropped `select_for_update` to break unrelated row-lock
contention), and two concurrent workers can each read the same pre-state
then commit last-writer-wins. The `max()` guard at `tasks.py:598` only
protects percentage regression *based on what each writer read* — it does
not serialize the readers, so a slower committer with a stale snapshot
clobbers a faster committer's blob.

`Job.progress` cannot be the source of truth for state-machine decisions
on async_api jobs. This PR makes that explicit at the one user-visible
site: the reaper's async_api guard. Reaper consults Redis directly.
`Job.progress` stays as the cosmetic mirror for the UI.

Related context:

- Lifecycle and bug taxonomy: `docs/claude/processing-lifecycle.md`
- Last-writer-wins admission: `ami/jobs/tasks.py:563-571`
- PR #1261 commit `50677444` removed `select_for_update`.

## Scope (narrow)

In scope:

- New `AsyncJobStateManager.all_tasks_processed() -> bool | None` —
  one Redis pipeline call (SCARD × 2 + GET) returning a tri-state.
- Replace the `not job.progress.is_complete()` read at `tasks.py:968`
  (reaper async_api guard) with the new Redis-backed check.
- WARNING log when Redis state is absent (`None` return), so we can
  monitor how often this fires.
- Tests for the 3-state matrix on `all_tasks_processed()` + a reaper
  test mirroring the 2521 shape (Redis empty, progress JSONB stuck at
  99.98% STARTED → reaper lands SUCCESS, not REVOKED).

Out of scope (filed as follow-ups):

- Race fix in `_update_job_progress` itself. Move counts to atomic
  Redis HINCRBY, or scope a row lock to microseconds via raw `jsonb_set`.
- Updating the other call sites that read `progress.is_complete()`
  (`tasks.py:654`, `:1331`, `:1361`, `:159`, `:496`). They are not
  affected by the clobber pattern under current operation — see
  "Why only the reaper" below.
- DB-count fallback for the `None` (Redis-gone) case. Today the
  WARNING log + `progress.is_complete()` fallback is sufficient. If
  the WARNING fires often enough to matter, follow-up adds a
  `pipeline.filter_processed_images()`-based check.
- Job-level method (`Job.processing_complete()`). Inline at the one
  call site that needs it; if a future site needs the same logic,
  extract then.
- UI changes. `Job.progress` shape is unchanged.
- `'CANCELLED' is not a valid JobState` crash in `tasks.py:1193`
  (`zombie_streams._drain_all`). Separate bug surfaced during 2521
  triage; legacy job row has a status not in the JobState enum.

## Why only the reaper

The clobber pattern in `_update_job_progress` exists at six call sites
that read `progress.is_complete()`. Only one is user-visible:

| Site | Race exposure | User-visible consequence |
|---|---|---|
| `tasks.py:968` reaper async_api guard | **Yes** — runs minutes after the racy writes have settled, sees the clobbered final state | **Yes — REVOKED instead of SUCCESS** |
| `tasks.py:654` cleanup gate inside `_update_job_progress` | Same writer is itself the racer; `is_complete()=False` after clobber prevents early cleanup | No — cleanup fires later from terminal-state path |
| `tasks.py:1331` `task_postrun` SUCCESS guard | None — fires at queue-completion, no NATS results yet, single writer | No |
| `tasks.py:1361` `task_failure` ASYNC_API guard | None — same single-writer moment | No |
| `tasks.py:159` `run_job` post-run log | None — log-gating only | No |
| `tasks.py:496` `MLJob.run` zero-images path | None — runs before any concurrent writers | No |

This PR fixes (1). The others either have a single writer at the moment
they run, or their failure mode is internal and self-correcting. If
monitoring later shows another site biting, expand then.

## Why not put the check inside `progress.is_complete()`

`JobProgress` is a Pydantic model — pure data. Adding Redis I/O behind
its `is_complete()` method:

- couples a serializable data shape to a side-effect-laden oracle
- silently makes every API serialization, log dump, and read trip
  Redis (caller doesn't see the I/O cost)
- the Pydantic instance has no `job_id` reference, so the method
  signature would have to grow an awkward `job_id=` argument
- breaks `JobProgress` reuse outside the Job context

Keep `JobProgress.is_complete()` as cosmetic Pydantic data check.
Do the Redis call at the state-machine call site that needs it.

## Design

### Tier 1 — Redis oracle on `AsyncJobStateManager`

```python
# ami/ml/orchestration/async_job_state.py
def all_tasks_processed(self) -> bool | None:
    """
    Truth signal for whether all NATS-tracked tasks have been processed
    out of both pending sets (process + results stages).

    Returns:
        True  — both pending sets are empty AND total > 0 (all tasks SREM'd)
        False — at least one pending set has members (real work outstanding)
        None  — Redis state absent (cleaned up, TTL expired, never initialized)
                Caller decides what to do; do not assume completeness.

    Scope: Redis tracks the per-image SREM lifecycle for the `process`
    and `results` stages only. It does NOT know about the `collect` stage
    or any future post-results stages. Callers that need "is the entire
    Job complete across ALL stages" must combine this with their own
    knowledge of stage layout.

    RedisError (transient connection issues) is logged and returned as
    None — a Redis blip should NOT flip a job to REVOKED on its own.
    """
    try:
        redis = self._get_redis()
        with redis.pipeline() as pipe:
            for stage in self.STAGES:
                pipe.scard(self._get_pending_key(stage))
            pipe.get(self._total_key)
            results = pipe.execute()
    except RedisError as e:
        logger.warning(
            f"Redis error reading all_tasks_processed for job {self.job_id}: {e}"
        )
        return None

    *pending_counts, total_raw = results
    if total_raw is None:
        return None
    total = int(total_raw)
    if total == 0:
        # Zero-images job: trivially "processed" — no NATS work to do.
        return True
    return all(count == 0 for count in pending_counts)
```

One Redis pipeline round-trip. SCARD is O(1) per key. Negligible at scale.

### Reaper guard replacement

```python
# ami/jobs/tasks.py:968 — replacement
is_terminal = celery_state in states.READY_STATES
is_async_api = job.dispatch_mode == JobDispatchMode.ASYNC_API
if is_async_api and celery_state in {states.SUCCESS, states.FAILURE}:
    processed = AsyncJobStateManager(job.pk).all_tasks_processed()
    if processed is False:
        # NATS tasks still pending in Redis. mark_lost_images_failed runs
        # before this and would have reconciled if it could; if we land
        # here with pending > 0, the reconciler couldn't help (consumer
        # gone, etc.) and REVOKE is the correct outcome.
        is_terminal = False
    elif processed is None:
        # Redis state gone — rare. Fall back to the racy progress oracle
        # but log so we know how often this path fires. If it fires
        # often, follow up with a DB-count fallback.
        logger.warning(
            "Reaper for job %s: Redis state absent, falling back to "
            "progress.is_complete()",
            job.pk,
        )
        if not job.progress.is_complete():
            is_terminal = False
    # processed is True -> trust Celery's terminal state, leave is_terminal as-is
```

Sync_api jobs hit none of this branch — they fall through `is_terminal =
celery_state in READY_STATES` exactly as today.

### Behavior change matrix

| Scenario | Today | After this PR |
|---|---|---|
| async_api job done; Redis empty; `progress` clobbered (2521 shape) | REVOKED | **SUCCESS** |
| async_api job mid-flight; Celery SUCCESS but Redis pending > 0 | REVOKED (was already, but for the wrong reason) | REVOKED (same outcome, correct reason: NATS tasks pending) |
| async_api job done; Redis pending == 0; `progress` accurate | SUCCESS | SUCCESS (no change) |
| async_api job done; Redis state cleaned up early | varies — depends on `progress` | falls back to `progress.is_complete()` with WARNING log |
| sync_api job at reaper | unchanged | unchanged |

### Tests

Extend `ami/ml/tests.py` (or `ami/jobs/tests/test_async_job_state.py`):

- `all_tasks_processed()` after fresh `initialize_job([...])` → False
  (all images still in pending sets)
- After SREM-ing every id from both stages → True
- After SREM-ing some → False
- With `total=0` (zero-images path) → True
- With Redis state never initialized → None
- With Redis state cleaned up via `cleanup()` → None
- Simulated `RedisError` on the pipeline → None + WARNING logged

Extend `ami/jobs/tests/test_tasks.py` — `TestCheckStaleJobs`:

- async_api job, Celery SUCCESS, Redis pending empty, `progress`
  hand-set to `process=99.98% STARTED processed=4509 remaining=1`
  (mirroring 2521) → reaper lands SUCCESS, not REVOKED. Asserts
  `is_terminal=True` path was taken.
- async_api job, Celery SUCCESS, Redis pending > 0 → REVOKED (no regression
  for genuine partial-completion).
- async_api job, Redis state absent, `progress.is_complete()=True`,
  Celery SUCCESS → SUCCESS via the fallback path. Assert WARNING log
  emitted.
- async_api job, Redis state absent, `progress.is_complete()=False`,
  Celery SUCCESS → REVOKED via the fallback path. Assert WARNING log emitted.
- sync_api job at reaper → behavior unchanged (existing tests cover).

### Logging

`logger.warning(...)` once per stale-async_api job per tick when Redis
state is absent. Format includes `job.pk` so we can grep.

Monitoring expectation post-deploy:

- Drop in REVOKED async_api jobs whose final `Job.progress` snapshot has
  `process>=99% STARTED` (the clobber signature).
- Low-rate WARNING lines from the Redis-gone fallback. High rate ==
  Redis cleanup is firing too aggressively, separate bug to chase.

## Acceptance criteria

- `all_tasks_processed()` exists with the three-state semantics.
- Reaper at `tasks.py:968` uses it; sync_api branch unchanged.
- Existing `ami.jobs` test suite stays green.
- New tests for the 3-state matrix + reaper-eats-2521-shape case pass.
- Manual chaos: dispatch real async_api job, wait until completion, then
  via Django shell hand-clobber `Job.progress` to mimic 2521. Wait 11
  min. Confirm reaper lands SUCCESS, not REVOKED. Confirm Redis was
  clean at decision time.

## Rollout

Single PR. No feature flag. The change is strictly additive at the call
site (one site replaced; no API or schema change). Deploy + monitor.

## Risks

- **Race window between Redis SREM and `all_tasks_processed()`**: a
  result that lands during the reaper's call could leave Redis briefly
  in an intermediate state. SCARD is atomic per-key; worst case is the
  snapshot misses a just-completed image and reports pending=1 → reaper
  defers → next tick sees pending=0 → SUCCESS. Bounded.
- **Redis-gone fallback rate**: if WARNING fires frequently in
  production, we punted too early on Tier 2 (DB count). Mitigation:
  add `pipeline.filter_processed_images()`-based fallback in a
  follow-up PR. Bounded — only fires when Redis state is absent AND the
  job is past the reaper cutoff.
- **Sync_api jobs unaffected**: dispatch_mode gate ensures non-async
  jobs hit the existing path. Verified by inspection + sync_api reaper
  tests.

## Follow-ups (separate PRs)

1. **Make `_update_job_progress` writes atomic.** Either tightly-scoped
   `select_for_update`, or move counts (`detections`, `classifications`,
   `captures`) to Redis HINCRBY counters with a separate sync task
   mirroring them into `Job.progress`. The cosmetic counter drift
   admitted at `tasks.py:563-571` becomes invisible, and the failure
   mode this PR addresses goes away even without the new method.
2. **DB-count fallback for the Redis-gone case** if monitoring shows
   the WARNING firing often. `pipeline.filter_processed_images()`
   against the Job's queued image set.
3. **Persist `queued_image_ids` on the Job row at dispatch** to make
   (2) cheaper.
4. **Fix `'CANCELLED' is not a valid JobState`** in `tasks.py:1193`.
5. **Expand `all_tasks_processed()` usage** to the other 5 sites if
   monitoring shows a clobber-driven failure at any of them.

## Diagnostic evidence (job 2521)

Captured from prod via `ami-devops` on 2026-04-29:

- Job row at REVOKE time:
  - `process=99.98% STARTED processed=4509 remaining=1`
  - `results=100% SUCCESS`
  - `progress.errors=[]`
- NATS at cleanup: `delivered=4510 ack_floor=4510 num_pending=0
  num_ack_pending=0 num_redelivered=0`
- Redis: all keys deleted at cleanup; pre-cleanup unknown but worker_ml
  log shows no `Stage 'X' progress lifted to 100% by max() guard`
  warning (the diagnostic hook for this race), suggesting both writers
  had stale reads.
- Worker log: `Updated job 2521 progress in stage 'process' to 100.0%`
  at 11:45:45.510, then a later `99.97782%` write to results, then
  silence for 14.5 min until reaper at 12:00:00.117.
- Reaper line: `Reaping stalled job: no progress for 14.2 min ... stages:
  collect=100.0% SUCCESS, process=100.0% STARTED, results=100.0% SUCCESS`
  — note the reaper's in-memory snapshot read shows 100% at the moment
  of REVOKE. The persisted blob at that moment was 99.98%. The
  `progress.is_complete()` call inside the guard re-read the persisted
  blob (or evaluated against the 100%-but-STARTED status, which fails
  the `final_states` check in `models.py:268`). Either way: guard
  fired, REVOKED.

This is the second case (status STARTED with progress=100% on the same
stage) — confirms the race is on the `status` field write, not just
the percentage. Both writers had stale snapshots; the slower one
overwrote the SUCCESS-status with STARTED.

Last updated: 2026-04-29.
