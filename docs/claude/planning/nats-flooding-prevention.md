# NATS Flooding Prevention & Event Loop Blocking

**Date:** 2026-02-16
**Context:** PSv2 integration test exposed Django becoming unresponsive due to NATS connection issues

## Problem

When NATS becomes temporarily unreachable or connections are interrupted, Django's entire HTTP server hangs. This was observed during integration testing when:

1. A stale job (1365) in STARTED status continuously attempted to reserve NATS tasks
2. The ADC worker spawned 16 DataLoader subprocesses, all hammering `/jobs/1365/tasks?batch=64`
3. Each `/tasks` request opens a new NATS connection and blocks a uvicorn worker thread
4. NATS connections timed out, triggering the nats.py client's reconnection loop
5. The reconnection loop consumed Django's shared event loop, blocking ALL HTTP requests
6. Even endpoints that don't use NATS (like `/ml/pipelines/`) became unreachable

## Root Causes

### 1. `nats.connect()` uses default reconnection behavior
**File:** `ami/ml/orchestration/nats_queue.py:26-29`
```python
async def get_connection(nats_url: str):
    nc = await nats.connect(nats_url)  # No connect_timeout, allow_reconnect defaults to True
    js = nc.jetstream()
    return nc, js
```

**Fix (APPLIED):** Added `connect_timeout=5, allow_reconnect=False, max_reconnect_attempts=0` to `nats.connect()`. Since we create a new connection per operation via context manager, we never need the client's built-in reconnection.

### 2. `/tasks` endpoint doesn't check job status
**File:** `ami/jobs/views.py:232-255`
The endpoint checked `dispatch_mode` but not job status. A FAILURE/SUCCESS job still tried to fetch from NATS.

**Fix (APPLIED):** Added guard: `if job.status in JobState.final_states(): return Response({"tasks": []})`.

### 3. `incomplete_only` filter only checked progress JSON, not top-level status
**File:** `ami/jobs/views.py:50-69` (`IncompleteJobFilter`)
The filter only checked the "results" stage status in the progress JSON. Jobs manually set to FAILURE (without updating progress stages) slipped through.

**Fix (APPLIED):** Added `queryset.exclude(status__in=JobState.final_states())` before the progress JSON check.

### 4. No timeout on stream/consumer operations
**File:** `ami/ml/orchestration/nats_queue.py:77-124`
`_ensure_stream()` and `_ensure_consumer()` call JetStream API without explicit timeouts. If NATS is slow, these block indefinitely.

**Status:** TODO

### 5. Leaked NATS connections from interrupted requests
When an HTTP request is interrupted (client disconnect, test script killed), the `TaskQueueManager.__aexit__` may not run, leaving a NATS connection open. With `allow_reconnect=True` (the old default), that connection's reconnection callbacks consumed the event loop.

**Status:** Mitigated by `allow_reconnect=False` fix.

### 6. `async_to_sync()` blocks Django worker threads
**Files:** `ami/jobs/views.py:253`, `ami/ml/orchestration/jobs.py:119`, `ami/jobs/tasks.py:191`

Every NATS operation wraps async code with `async_to_sync()`, which creates or reuses a thread-local event loop. If the async operation hangs (stuck NATS connection), the Django worker thread is permanently blocked.

**Status:** TODO — wrap with `asyncio.wait_for()` inside the async function.

### 7. Stale ADC workers compete for tasks (test infrastructure issue)
The test script starts an ADC worker but doesn't kill stale workers from previous runs. With 2 GPUs, `mp.spawn(nprocs=2)` forks 2 child processes. If a previous worker is still running, its DataLoader subprocesses race with the new worker for NATS messages. In the 2026-02-16 test, 147 `/tasks` requests were logged — the stale worker consumed all 20 NATS messages, leaving 0 for the new worker.

**Fix:** Add `pkill -f "ami worker"` cleanup before starting the worker in the test script.

## Additional TODOs from Integration Testing

### 7. `/tasks/` endpoint should support multiple pipelines
The endpoint should allow workers to pass in multiple pipeline slugs, or return all available tasks for projects the token has access to (no pipeline filter = all).

**Status:** TODO

### 8. ADC worker should use trailing slashes
The ADC worker requests `/api/v2/jobs/1365/tasks?batch=64` without trailing slash, causing 301 redirects. Each redirect doubles the request overhead.

**Status:** TODO (ADC-side fix in `ami-data-companion`)

### 9. `dispatch_mode` should be set on job init, not `run()`
Currently `dispatch_mode` is set when the job starts running. It should be set at job creation time so the API can filter by it before the job runs.

**Status:** TODO

### 10. Processing service online status (GitHub #1122)
Show online status of registered processing services.
**See:** https://github.com/RolnickLab/antenna/issues/1122

### 11. Show which workers pick up a job/task (GitHub #1112)
At minimum, log which worker processes each task.
**See:** https://github.com/RolnickLab/antenna/issues/1112

## Applied Changes Summary

| File | Change | Status |
|------|--------|--------|
| `ami/ml/orchestration/nats_queue.py:26-32` | `connect_timeout=5, allow_reconnect=False` | APPLIED |
| `ami/jobs/views.py:237-238` | Guard `/tasks` for terminal status jobs | APPLIED |
| `ami/jobs/views.py:59` | `incomplete_only` also checks top-level status | APPLIED |

## Remaining TODOs

| Priority | Issue | Impact |
|----------|-------|--------|
| P1 | Timeout on JetStream stream/consumer ops | Prevents indefinite blocking |
| P1 | `async_to_sync()` timeout wrapper | Prevents thread exhaustion |
| P2 | `/tasks/` multi-pipeline support | Worker efficiency |
| P2 | ADC trailing slashes | Removes 301 overhead |
| P2 | `dispatch_mode` on job init | Correct filtering at creation time |
| P3 | Stale job auto-cleanup (Celery Beat) | Prevents future flooding |
| P3 | Circuit breaker for NATS failures | Graceful degradation |
| P3 | #1122: Processing service online status | UX |
| P3 | #1112: Worker tracking in logs | Observability |

## Related Files

| File | Lines | What |
|------|-------|------|
| `ami/ml/orchestration/nats_queue.py` | 26-32 | `get_connection()` — FIXED with timeouts |
| `ami/ml/orchestration/nats_queue.py` | 77-124 | Stream/consumer ops — needs timeouts |
| `ami/ml/orchestration/nats_queue.py` | 159-214 | `reserve_task()` — has timeout but connection may block |
| `ami/jobs/views.py` | 50-69 | `IncompleteJobFilter` — FIXED |
| `ami/jobs/views.py` | 237-238 | `/tasks` status guard — FIXED |
| `ami/jobs/views.py` | 243-256 | `/tasks/` endpoint — `async_to_sync()` blocks thread |
| `ami/ml/orchestration/jobs.py` | 119 | `queue_images_to_nats()` — `async_to_sync()` blocks thread |
| `ami/jobs/tasks.py` | 184-199 | `_ack_task_via_nats()` — per-ACK connection (expensive) |
| `docs/claude/debugging/nats-triage.md` | Full | Previous NATS debugging findings |
| `docs/claude/nats-todo.md` | Full | NATS infrastructure improvements tracker |
