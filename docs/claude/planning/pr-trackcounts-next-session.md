# Next Session: carlos/trackcounts PR Review

## Context

We're reviewing and cleaning up a PR that adds cumulative count tracking (detections, classifications, captures, failed images) to the async (NATS) job pipeline. The PR is on branch `carlos/trackcounts`.

## Working with worktrees and remotes

There are two related branches on different remotes/worktrees:

| Branch | Remote | Worktree | PR |
|--------|--------|----------|-----|
| `carlos/trackcounts` | `origin` (RolnickLab) | `/home/michael/Projects/AMI/antenna` (main) | trackcounts PR |
| `carlosg/natsconn` | `uw-ssec` (uw-ssec) | `/home/michael/Projects/AMI/antenna-natsconn` | #1130 |

**Key rules:**
- `carlosg/natsconn` pushes to `uw-ssec`, NOT `origin`
- The worktree at `antenna-natsconn` is detached HEAD — use `git push uw-ssec HEAD:refs/heads/carlosg/natsconn`
- To run tests from the worktree, mount only `ami/` over the main compose: `docker compose run --rm -v /home/michael/Projects/AMI/antenna-natsconn/ami:/app/ami:z django python manage.py test ... --keepdb`
- Container uses Pydantic v1 — use `.dict()` / `.json()`, NOT `.model_dump()` / `.model_dump_json()`

## Completed commits (on top of main merge)

1. `a5ff6f8a` — Rename `_get_progress` → `_commit_update` in TaskStateManager
2. `337b7fc8` — Unify `FAILURE_THRESHOLD` constant + convert TaskProgress to dataclass
3. `89111a05` — Rename `TaskProgress` → `JobStateProgress`

## Remaining work

### 1. Review: Is `JobStateProgress` the right abstraction?

**Question:** What is `TaskStateManager` actually tracking, and does `JobStateProgress` reflect that correctly?

There are two parallel progress tracking systems:
- **Django side:** `Job.progress` → `JobProgress` (Pydantic model, persisted in DB)
  - Has multiple stages (collect, process, results)
  - Each stage has its own status, progress percentage, and arbitrary params
  - `is_complete()` checks all stages
- **Redis side:** `TaskStateManager` → `JobStateProgress` (dataclass, ephemeral in Redis)
  - Tracks pending image IDs per stage (process, results)
  - Tracks cumulative counts: detections, classifications, captures, failed
  - Single flat object — no per-stage breakdown of counts

The disconnect: Redis tracks **per-stage pending images** (separate pending lists for "process" and "results" stages) but returns **job-wide cumulative counts** (one detections counter, one failed set). So `JobStateProgress` is a hybrid — stage-scoped for image completion, but job-scoped for counts.

**Should counts be per-stage?** For example, "failed" in the process stage means images that errored during ML inference. But could there be failures in the results stage too (failed to save)? The sync path tracks `request_failed_images` (process failures) separately from `failed_save_tasks` (results failures). The async path currently lumps all failures into one set.

**Key files to read:**
- `ami/ml/orchestration/task_state.py` — `TaskStateManager` and `JobStateProgress`
- `ami/jobs/tasks.py:62-185` — `process_nats_pipeline_result` (async path, uses TaskStateManager)
- `ami/jobs/models.py:466-582` — `MLJob.process_images` (sync path, tracks counts locally)
- `ami/jobs/models.py:134-248` — `JobProgress`, `JobProgressStageDetail`, `is_complete()`

### 2. Remove `complete_state` parameter

Plan is written at: `docs/claude/planning/pr-trackcounts-complete-state-removal.md`

Summary: Remove `complete_state` from `_update_job_progress`. Jobs always complete as SUCCESS. Failure counts are tracked as stage params but don't affect overall status. "Completed with failures" state deferred to future PR.

**Files to modify:**
- `ami/jobs/tasks.py:97-179, 205-223` — remove complete_state logic
- `ami/ml/orchestration/tests/test_cleanup.py:164-168` — update test calls
- `ami/jobs/test_tasks.py` — update any affected tests

### 3. PR assessment doc

Full review written at: `docs/claude/planning/pr-trackcounts-review.md`
