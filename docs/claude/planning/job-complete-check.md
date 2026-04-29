# Plan: reusable `Job.is_actually_complete()` (fix/job-complete-check)

## Why

Production job 2521 (project 192, ~4510 images, async_api) finished with all
4510 NATS messages acked and Redis pending sets empty, but `Job.progress`
JSONB had `process=99.98% STARTED processed=4509 remaining=1`. The
`jobs_health_check` reaper at the 10-min cutoff:

1. `mark_lost_images_failed` correctly skipped the job (Redis pending was
   empty, so `lost_ids` was empty, which is the documented skip path).
2. `check_stale_jobs` found Celery `state=SUCCESS` but the async_api guard at
   `ami/jobs/tasks.py:968` consults `job.progress.is_complete()`, which
   returned False because of the clobbered `process` stage.
3. Reaper REVOKEd the job. Result: 5058 detections / 8129 classifications
   already saved to DB, but the Job row reads REVOKED.

PR #1244's reconciler is the wrong tool for this symptom — there is nothing
to reconcile in Redis. The bug is upstream: `_update_job_progress` writes
the entire `progress` JSONB blob without a row lock (see PR #1261, which
removed `select_for_update` to fix unrelated row-lock contention), and two
concurrent workers can each read the same pre-state then commit
last-writer-wins. The `max()` guard at `tasks.py:598` only protects
percentage regression *based on what the writer read* — it does not
serialize the readers, so a slower committer with a stale snapshot
clobbers a faster committer's blob.

`Job.progress` cannot be the source of truth for state-machine decisions.
This PR makes that explicit: introduce a reliable completion check backed
by Redis (which uses atomic SREM/SADD and is not racy), with a DB-count
fallback for jobs whose Redis state has been cleaned up. `Job.progress`
stays as the cosmetic mirror for the UI.

Related context:

- Lifecycle and bug taxonomy: `docs/claude/processing-lifecycle.md`
- Last-writer-wins admission: `ami/jobs/tasks.py:563-571`
- PR #1261 commit `50677444` removed `select_for_update` to fix contention.

## Scope

In scope:

- New `JobCompletionSnapshot` dataclass + `AsyncJobStateManager.summarize()`.
- New `Job.is_actually_complete()` method with Tier 1 (Redis) → Tier 2
  (DB count) → Tier 3 (`progress.is_complete()` for sync_api) fallback.
- WARNING log whenever Tier 2 fires, so we can monitor frequency and
  catch unexpected fallbacks.
- Replace `progress.is_complete()` reads at the four state-machine call
  sites that currently consult it.
- Tests covering the 4-way matrix (dispatch_mode × Redis-present-or-not).

Out of scope:

- Race fix in `_update_job_progress` itself. That is a separate, larger
  refactor (move counts to atomic Redis counters, or scope a row lock to
  microseconds via raw `jsonb_set`). Filed as follow-up: see
  `### Follow-ups` below.
- UI changes. `Job.progress` stays as-is. The new method is backend-only.
- Touching `mark_lost_images_failed`. The reconciler's behavior is
  correct for its intended bug (NATS-lost messages); 2521 was a different
  failure that this PR addresses upstream.

## Design

### Tier 1 — Redis oracle

`AsyncJobStateManager.summarize() -> JobCompletionSnapshot`. Single
Redis pipeline round-trip:

```python
pipe.scard(self._get_pending_key("process"))
pipe.scard(self._get_pending_key("results"))
pipe.scard(self._failed_key)
pipe.get(self._total_key)
```

```python
@dataclass
class JobCompletionSnapshot:
    state_present: bool                 # total_raw is not None
    total: int                          # 0 when state_present=False
    pending_per_stage: dict[str, int]   # {"process": N, "results": M}
    failed: int
    is_complete: bool                   # state_present AND all pending == 0

    # Convenience for callers:
    @property
    def all_acked(self) -> bool:
        return self.state_present and all(v == 0 for v in self.pending_per_stage.values())
```

`is_complete` is True only when state_present AND every stage's pending
set is empty. A job whose Redis state is gone returns
`state_present=False`, regardless of stage state — caller decides what to
do via Tier 2 fallback.

`RedisError` is swallowed inside `summarize()` and returns
`state_present=False`. We do NOT propagate Redis transients up to the
reaper — a Redis blip should not flip a job to REVOKED.

### Tier 2 — DB Detection-row count

When Redis state is gone, query DB to determine whether all queued images
have detections from the job's pipeline algorithms:

```python
def _is_complete_via_db(self) -> bool:
    """Slow but durable. Only runs when Redis state is missing
    (post-cleanup, post-TTL, or post-restart). Logs a WARNING so
    we know how often we fall through to this path.
    """
    queued_ids = self._collected_image_ids()  # see below
    if not queued_ids:
        return True  # zero-images job is trivially complete
    unprocessed = self.pipeline.filter_processed_images(
        SourceImage.objects.filter(pk__in=queued_ids)
    ).only("pk")
    is_complete = not unprocessed.exists()
    self.logger.warning(
        "job %s: Redis state gone, fell back to DB detection-count check; "
        "queued=%d, unprocessed=%d, is_complete=%s",
        self.pk, len(queued_ids), unprocessed.count(), is_complete,
    )
    return is_complete
```

`self._collected_image_ids()`: derive from `Job.source_image_collection`,
`Job.source_image_single`, or `Job.deployment` exactly the way
`MLJob.run`/`pipeline.collect_images` does. Or, if the cost of
re-resolving is too high, persist the queued id list at dispatch time.
The `summarize()` payload includes `total` from Redis but Tier 2 needs
the full id set, so we cannot rely on Redis alone here.

For the first PR cut, derive on the fly via `pipeline.collect_images()`
to avoid a schema change. If profiling shows this is slow at 5k+ images,
follow-up adds a `Job.queued_image_ids` jsonb column or similar.

### Tier 3 — sync_api fallback

`progress.is_complete()` for non-async_api jobs. Unchanged. Sync mode
does not use Redis at all, and its writes are serialized by the single
Celery task driving each stage.

### `Job.is_actually_complete()`

```python
def is_actually_complete(self) -> bool:
    """Source-of-truth completion check. Use everywhere instead of
    self.progress.is_complete() for state-machine decisions.
    self.progress.is_complete() remains valid for cosmetic/UI reads.
    """
    if self.dispatch_mode == JobDispatchMode.ASYNC_API:
        snap = AsyncJobStateManager(self.pk).summarize()
        if snap.state_present:
            return snap.is_complete
        return self._is_complete_via_db()
    return self.progress.is_complete()
```

Method on the Job model, not a free function — lets call sites read like
`if not job.is_actually_complete(): ...` matching the existing
`progress.is_complete()` pattern.

### Call sites to update

| File:line | Current call | Replacement |
|---|---|---|
| `ami/jobs/tasks.py:968` (reaper async_api guard) | `not job.progress.is_complete()` | `not job.is_actually_complete()` |
| `ami/jobs/tasks.py:654` (`_update_job_progress` cleanup gate) | `if job.progress.is_complete():` | `if job.is_actually_complete():` |
| `ami/jobs/tasks.py:1331` (`task_postrun` SUCCESS guard) | `not job.progress.is_complete()` | `not job.is_actually_complete()` |
| `ami/jobs/tasks.py:1361` (`task_failure` ASYNC_API guard) | `not job.progress.is_complete()` | `not job.is_actually_complete()` |
| `ami/jobs/models.py:496` (zero-images path in `MLJob.run`) | `if job.progress.is_complete():` | leave as-is — runs before Redis is initialized |
| `ami/jobs/models.py:159` (`run_job` post-task log) | `not job.progress.is_complete()` | leave as-is — log gating only, not state-machine |

The four state-machine sites (rows 1-4) are the ones that decide SUCCESS
vs REVOKED vs deferred-cleanup. They all currently misread the clobbered
`progress.is_complete()`. The two leave-as-is rows are pre-Redis
initialization or log-only — the replacement would be no-op or wrong.

### Tests

`ami/jobs/tests/test_async_job_state.py` (new file or extend existing):

- `summarize()` against fresh init (state_present=True, all pending=total)
- `summarize()` mid-flight (some pending, some processed)
- `summarize()` complete (state_present=True, all pending=0, is_complete=True)
- `summarize()` cleaned up (state_present=False, is_complete=False)
- `summarize()` Redis transient (RedisError → state_present=False)

`ami/jobs/tests/test_job_completion.py` (new):

- `Job.is_actually_complete()` — async_api + Redis present + all pending=0 → True
- async_api + Redis present + pending>0 → False (mid-flight defer)
- async_api + Redis gone + DB shows all detections present → True
- async_api + Redis gone + DB shows missing detections → False (logs WARNING)
- sync_api → falls through to `progress.is_complete()`, unchanged
- async_api with 2521 shape (Redis empty, progress JSONB stuck at 99.98%) → True

`ami/jobs/tests/test_tasks.py` extension:

- Reaper reaches the async_api guard with stale `progress` (process=99.98%
  STARTED) but Redis empty → lands SUCCESS, not REVOKED. Mirrors 2521.

### Logging

Tier 2 fires a WARNING with `job_id, queued_count, unprocessed_count,
is_complete`. This is the signal we use to monitor:

- How often do we fall through to DB? (Should be rare. High rate ==
  Redis cleanup is firing too aggressively, separate bug.)
- When we fall through, do we usually find complete or incomplete?
  (Mostly complete == Redis TTL expiring on long-finished jobs. Mostly
  incomplete == genuine partial-completion that the reaper will REVOKE,
  which is the correct outcome.)

Tier 1 is silent in the happy path; only ERRORS log on RedisError.

## Acceptance criteria

- All four state-machine call sites use `Job.is_actually_complete()`.
- Existing test suite `ami.jobs` stays green.
- New tests for the 6+ matrix cases pass.
- E2E run on a real ADC against a 50+ image collection lands SUCCESS.
- Manual chaos test: dispatch real job, manually clobber `Job.progress`
  to mimic 2521 shape via Django shell, wait 11 min, verify reaper lands
  SUCCESS not REVOKED. Verify Redis pending was empty at decision time.
- Tier 2 WARNING log appears when expected and only when expected.

## Rollout

Single PR. No feature flag. The new method strictly fixes a
known-broken path; no breaking change. Deploy + monitor reaper logs for:

- Drop in REVOKEd async_api jobs that have `progress=~100%` in their final
  Job row state.
- Any unexpected uptick in `fell back to DB detection-count check`
  WARNING lines.

## Risks

- **DB fallback is slow on big jobs**: bounded — only fires after Redis
  cleanup, on a stale job at the reaper tick. Worst case one slow query
  per stale job per 15-min beat.
- **`pipeline.collect_images` re-resolves the queued list**: if the
  Collection has changed since dispatch (rare for completed jobs but
  possible), the recomputed id list may not match the originally queued
  list. Acceptable for v1 — the WARNING log will show the count and we
  can iterate.
- **Race window between Redis SREM and `summarize()`**: a result that
  lands during the reaper's `summarize()` call could leave Redis briefly
  in an inconsistent intermediate state. SCARD is atomic per-key, so the
  worst case is the snapshot misses a just-completed image and reports
  pending=1 → reaper waits another tick → next tick sees 0 → SUCCESS.
  Bounded.

## Follow-ups (separate PRs)

1. **Make `_update_job_progress` writes atomic.** Either re-introduce a
   tightly-scoped `select_for_update`, or move counts (`detections`,
   `classifications`, `captures`) to Redis HINCRBY counters and have a
   separate sync task mirror them into `Job.progress` periodically. The
   cosmetic counter drift admitted at `tasks.py:563-571` becomes invisible
   under (1), and the failure mode in this PR's plan goes away even
   without `is_actually_complete()`.
2. **Persist `queued_image_ids` on the Job row at dispatch time.**
   Replaces the on-the-fly `pipeline.collect_images` call in Tier 2.
3. **Fix `'CANCELLED' is not a valid JobState`** in
   `ami/jobs/tasks.py:1193` (`_drain_all`). Separate bug surfaced during
   2521 investigation — `zombie_streams` check is throwing every tick on
   a legacy job row whose `status='CANCELLED'` is not in the JobState
   enum (only `CANCELING` / `REVOKED` are valid).

## Diagnostic evidence (job 2521)

Captured from prod via `ami-devops` on 2026-04-29:

- Job row at REVOKE time:
  - `process=99.98% STARTED processed=4509 remaining=1`
  - `results=100% SUCCESS`
  - `progress.errors=[]`
- NATS at cleanup: `delivered=4510 ack_floor=4510 num_pending=0
  num_ack_pending=0 num_redelivered=0`
- Redis: all keys deleted at cleanup; pre-cleanup unknown but worker_ml
  log shows no `Stage 'X' progress lifted to 100% by max() guard` warning
  (the diagnostic hook for this race), suggesting both writers had stale
  reads.
- Worker log: `Updated job 2521 progress in stage 'process' to 100.0%` at
  11:45:45.510, then a later `99.97782%` write to results, then silence
  for 14.5 min until reaper at 12:00:00.117.
- Reaper line: `Reaping stalled job: no progress for 14.2 min ... stages:
  collect=100.0% SUCCESS, process=100.0% STARTED, results=100.0% SUCCESS`
  — note the reaper's in-memory snapshot read shows 100% at the moment of
  REVOKE. The persisted blob at that moment was 99.98%. The
  `progress.is_complete()` call inside the guard re-read the persisted
  blob (or evaluated against the 100%-but-STARTED status, which fails the
  `final_states` check in `models.py:268`). Either way: guard fired,
  REVOKED.

This is the second case (status STARTED with progress=100% on the same
stage) — it confirms the race is on the `status` field write, not just
the percentage. Both writers had stale snapshots; the slower one
overwrote the SUCCESS-status with STARTED.

Last updated: 2026-04-29.
