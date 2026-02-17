# PSv2 Integration Test Session - 2026-02-16

## Summary

Attempted end-to-end PSv2 integration test on main. Discovered several blocking issues preventing completion.

## Test Setup

- Antenna: main branch, all services via docker compose
- ADC: main branch, conda env ami-py311, freshly installed
- Script: `scripts/psv2_integration_test.sh 20`

## What Worked

- Pipeline registration: OK (10 pipelines, all models loaded)
- Collection creation & population: OK
- Job creation with `start_now=true`: OK
- Image queuing to NATS: OK (20 images published)
- ADC worker task fetching from NATS: OK (tasks retrieved)

## What Failed

### 1. ADC worker reports "Done, detections: 0" — stale worker stole tasks
- Root cause: the stale ADC worker from test run #1 was never killed
- It found job 1377 and consumed all 20 NATS messages before the new worker
- Antenna logs show 147 `/tasks?batch=64` requests, ~35 distinct source ports
- The new worker (AMI_NUM_WORKERS=0) found an empty NATS queue → "No more tasks"
- The 39-second delay was caused by queuing behind stale worker requests on single uvicorn thread
- **Not an ADC code bug** — the stale worker race condition caused 0 results
- **Next test must kill ALL ADC worker processes before starting**
- **TODO (test script)**: Add `pkill -f "ami worker"` cleanup step before starting worker

### 2. Django overloaded by concurrent /tasks requests
- uvicorn runs with 1 worker in dev mode (no `--workers` flag)
- ADC spawns 16 DataLoader subprocesses by default, all hit `/tasks` simultaneously
- Each request blocks on NATS connection + operation (up to 5s with our fix)
- 16 × 5s = 80s serialized wait → all requests timeout
- **Fix applied**: Set `AMI_NUM_WORKERS=0` in test script (1 subprocess)
- **TODO**: Add `--workers 4` to uvicorn dev config, or connection pooling

### 3. Stale NATS connections block Django event loop
- `nats.connect()` defaulted to `allow_reconnect=True` with long timeouts
- Leaked connections from interrupted requests spawned reconnection loops
- These loops consumed the shared async event loop, blocking ALL requests
- **Fix applied**: `connect_timeout=5, allow_reconnect=False` in `get_connection()`

### 4. Stale jobs not filtered by incomplete_only
- `IncompleteJobFilter` only checked progress JSON stages, not top-level `status`
- Jobs manually set to FAILURE without progress update slipped through
- ADC worker picked up stale jobs and hammered `/tasks` endlessly
- **Fix applied**: Also exclude `status__in=JobState.final_states()`

### 5. /tasks endpoint doesn't guard against terminal jobs
- A FAILURE/SUCCESS/REVOKED job still tried to fetch from NATS
- **Fix applied**: Return empty `{"tasks": []}` for terminal status jobs

### 6. RabbitMQ stale connections
- After days of uptime, Django's AMQP connection to RabbitMQ goes stale
- `ConnectionResetError: [Errno 104]` when enqueuing Celery tasks
- **Fix**: Restart Django/Celery or full `docker compose down && up`

## Applied Code Changes

### `ami/ml/orchestration/nats_queue.py:26-32`
```python
async def get_connection(nats_url: str):
    nc = await nats.connect(
        nats_url,
        connect_timeout=5,
        allow_reconnect=False,
        max_reconnect_attempts=0,
    )
```

### `ami/jobs/views.py:59`
```python
# IncompleteJobFilter - also exclude by top-level status
queryset = queryset.exclude(status__in=JobState.final_states())
```

### `ami/jobs/views.py:237-238`
```python
# /tasks endpoint - guard against terminal jobs
if job.status in JobState.final_states():
    return Response({"tasks": []})
```

### `scripts/psv2_integration_test.sh:135`
```bash
AMI_NUM_WORKERS=0 ami worker --pipeline quebec_vermont_moths_2023 2>&1
```

## Remaining TODOs

Full list in `docs/claude/planning/nats-flooding-prevention.md`.

Key items:
1. **Re-run integration test** — kill all stale ADC workers first, then test with clean state
2. **Test script: kill stale workers** — add `pkill -f "ami worker"` before starting
3. **NATS connection pooling** — PR #1130 attempted this but had issues
4. **uvicorn workers** — add `--workers 4` to dev config
5. **JetStream operation timeouts** — `_ensure_stream()`, `_ensure_consumer()` have no timeouts
6. **ADC trailing slashes** — causes 301 redirects on every request
7. **`dispatch_mode` on job init** — should be set at creation, not run()
8. **Multi-pipeline /tasks endpoint** — let workers request tasks for multiple pipelines
9. **GitHub #1122** — processing service online status
10. **GitHub #1112** — worker tracking in logs

## Next Session Prompt

```
Continue PSv2 integration testing. Key files changed (uncommitted):
- ami/ml/orchestration/nats_queue.py:26-32 (NATS connection safety)
- ami/jobs/views.py:59,237-238 (stale job filtering + /tasks guard)
- scripts/psv2_integration_test.sh:135 (reduced worker count)

The 0-detections issue was caused by a stale ADC worker from test run #1
consuming all NATS messages. Not a code bug. Kill ALL "ami worker" processes
before re-running.

Add pkill cleanup to test script, commit fixes, re-run test.

Full findings: docs/claude/planning/nats-flooding-prevention.md
Session notes: docs/claude/sessions/2026-02-16-psv2-integration-test.md
```
