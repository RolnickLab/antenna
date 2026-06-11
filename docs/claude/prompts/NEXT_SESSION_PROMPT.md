# Next session: implement `fix/job-complete-check`

Branch: `fix/job-complete-check` at commit `10cdac28` (worktree
`/home/michael/Projects/AMI/antenna/.claude/worktrees/dangling-tasks`).

Plan: `docs/claude/planning/job-complete-check.md` (read first — has the
full design, risks, follow-ups, and 2521 evidence).

## TL;DR

Production job 2521 ended REVOKED because `_update_job_progress`
(`ami/jobs/tasks.py:556`) writes the entire `Job.progress` JSONB blob
without a row lock since PR #1261 dropped `select_for_update`. Two
concurrent workers raced; slower committer with `processed=4509
remaining=1` clobbered the faster committer's `processed=4510 SUCCESS`
write. NATS + Redis both showed all 4510 tasks done; only `Job.progress`
lied. Reaper at `tasks.py:968` consults `progress.is_complete()` →
False (because clobbered) → REVOKED.

Fix: add `AsyncJobStateManager.all_tasks_processed() -> bool | None`,
inline at the reaper guard. Sync_api unaffected. Other 5 `progress.is_complete()`
readers untouched (not bitten by clobber). Pydantic `JobProgress` stays
pure data — Redis I/O lives on the manager class.

## Implementation steps

### 1. `all_tasks_processed()`

File: `ami/ml/orchestration/async_job_state.py`

After `get_pending_image_ids()` (around line 229), add:

```python
def all_tasks_processed(self) -> bool | None:
    """Tri-state truth signal for NATS-task SREM completeness across both
    process and results pending sets.

    True  — both pending sets empty AND total > 0 (or total == 0)
    False — at least one pending set has members
    None  — Redis state absent (cleaned up, expired, never initialized,
            or transient RedisError)

    Scope: tracks NATS task lifecycle only; does not know about `collect`
    or any future post-results stages.
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
    if int(total_raw) == 0:
        return True
    return all(count == 0 for count in pending_counts)
```

### 2. Reaper guard replacement

File: `ami/jobs/tasks.py:963-969`

Replace:
```python
is_terminal = celery_state in states.READY_STATES
is_async_api = job.dispatch_mode == JobDispatchMode.ASYNC_API
if is_async_api and celery_state in {states.SUCCESS, states.FAILURE} and not job.progress.is_complete():
    is_terminal = False
```

With:
```python
is_terminal = celery_state in states.READY_STATES
is_async_api = job.dispatch_mode == JobDispatchMode.ASYNC_API
if is_async_api and celery_state in {states.SUCCESS, states.FAILURE}:
    processed = AsyncJobStateManager(job.pk).all_tasks_processed()
    if processed is False:
        is_terminal = False
    elif processed is None:
        logger.warning(
            "Reaper for job %s: Redis state absent, falling back to "
            "progress.is_complete()",
            job.pk,
        )
        if not job.progress.is_complete():
            is_terminal = False
    # processed is True -> trust Celery's terminal state
```

Need import: `from ami.ml.orchestration.async_job_state import AsyncJobStateManager`
(check if already imported at top of file).

### 3. Tests

**`ami/ml/tests.py`** — add `TestAsyncJobStateManagerAllTasksProcessed`:
- fresh `initialize_job([...])` → False
- after SREM-ing every id from both stages → True
- after SREM-ing only one stage → False
- `total=0` zero-images → True
- never initialized → None
- after `cleanup()` → None
- mocked `RedisError` on pipeline → None + WARNING

**`ami/jobs/tests/test_tasks.py::TestCheckStaleJobs`** — add cases:
- async_api + Celery SUCCESS + Redis empty + `progress` clobbered to
  `process=99.98% STARTED processed=4509 remaining=1` → SUCCESS, not REVOKED
  (the 2521 case)
- async_api + Celery SUCCESS + Redis pending > 0 → REVOKED
- async_api + Redis state absent + `progress.is_complete()=True` → SUCCESS
  via fallback + assert WARNING log
- async_api + Redis state absent + `progress.is_complete()=False` → REVOKED
  via fallback + assert WARNING log
- sync_api → existing behavior unchanged

### 4. Run tests

```bash
cd /home/michael/Projects/AMI/antenna/.claude/worktrees/dangling-tasks
docker compose -f docker-compose.ci.yml run --rm django \
  python manage.py test ami.ml.tests.TestAsyncJobStateManagerAllTasksProcessed ami.jobs.tests.test_tasks --keepdb
```

If tests pass, run the full `ami.jobs` suite:
```bash
docker compose -f docker-compose.ci.yml run --rm django \
  python manage.py test ami.jobs --keepdb
```

### 5. E2E chaos validation

Per the chaos pattern in `docs/claude/debugging/chaos-scenarios.md`:

1. Dispatch real async_api job (50+ images) on local stack with ADC
   running. Wait until SUCCESS naturally.
2. Via Django shell, hand-clobber `Job.progress` to mimic 2521:
   ```python
   from ami.jobs.models import Job, JobState
   j = Job.objects.get(pk=<id>)
   j.status = JobState.STARTED
   j.progress.update_stage("process", status=JobState.STARTED, progress=0.9998,
                           processed=N-1, remaining=1, failed=0)
   j.updated_at = j.updated_at - datetime.timedelta(minutes=15)
   j.save()
   ```
3. Trigger `jobs_health_check` manually:
   ```python
   from ami.jobs.tasks import jobs_health_check
   jobs_health_check()
   ```
4. Verify: job lands SUCCESS (not REVOKED). Verify Redis still empty
   (cleanup runs from terminal-state path).

### 6. PR

```bash
gh pr create --title "fix(jobs): reaper checks Redis directly via all_tasks_processed" --body "..."
```

PR body template — start from the plan doc's "Why", "Behavior change
matrix", and "Risks" sections. Reference job 2521.

## Pre-requisites and gotchas

- Worktree currently at `dangling-tasks` path but on branch
  `fix/job-complete-check`. `git status` should be clean.
- Pydantic v1 in container — `.dict()` / `.json()` not `.model_dump()`.
- CI compose file is `docker-compose.ci.yml` for tests with `--keepdb`.
- Stale RabbitMQ connections after days: restart Django/Celery if
  enqueueing throws `ConnectionResetError`.
- `cachalot_disabled()` decorator wraps `process_nats_pipeline_result`
  — not relevant here but flagged in case a related test fails on cache.

## Saved diagnostic logs from 2521

On the ami-devops host (not local):
- `/tmp/job2521_celery_72h.log`
- `/tmp/job2521_worker_jobs_72h.log`
- `/tmp/job2521_worker_ml_72h.log`
- `/tmp/job2521_worker_default_72h.log`
- `/tmp/job2521_beat_72h.log`

If next session needs to re-grep, dispatch a subagent in
`~/Projects/AMI/ami-devops/` rather than re-fetching from prod.

## Open follow-up tickets to file (not in this PR)

1. Make `_update_job_progress` writes atomic. Either re-introduce a
   tightly-scoped `select_for_update`, or move counts to Redis HINCRBY
   counters with separate sync task. Solves the underlying race that
   this PR works around.
2. DB-count fallback for the Redis-gone case. Add only if the WARNING
   log fires often in production.
3. Persist `queued_image_ids` on Job at dispatch — makes (2) cheaper.
4. Fix `'CANCELLED' is not a valid JobState` crash in
   `ami/jobs/tasks.py:1193` (`zombie_streams._drain_all`). Throws
   every beat tick on a legacy job row whose status is not in the
   JobState enum.
5. Expand `all_tasks_processed()` usage to other 5 `progress.is_complete()`
   sites if monitoring shows clobber-driven failures elsewhere.

## Branch state

```
$ git log --oneline fix/job-complete-check ^main
10cdac28 docs(jobs): narrow plan to reaper-only Redis check via all_tasks_processed
091e2fc7 docs(jobs): plan reusable Job.is_actually_complete() backed by Redis
```

(091e2fc7 is the original broader plan — superseded by 10cdac28. Do NOT
implement from 091e2fc7.)
