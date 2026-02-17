# Next Session: Integration Test with Batch NATS Fetch

## Context

PR #1135 (`fix/nats-connection-safety`) now has 4 commits:

1. `394ce55d` — NATS connection safety (connect_timeout, no reconnect) + stale job filtering + /tasks terminal guard + test script cleanup
2. `07cc18ac` — Session notes
3. `ddd560d0` — Updated session notes with test run #3 results
4. `367343c1` — **Batch NATS task fetch** (`reserve_tasks()` replaces N×1 `reserve_task()`)

Previous integration test (run #3) passed end-to-end (job 1380, 20/20 images, SUCCESS) but took ~11 minutes due to a 5-minute NATS `ack_wait` delay. Root cause: the `/tasks` endpoint made 320 NATS round trips for `batch=64`, exceeding the ADC's HTTP timeout. Tasks were consumed at the NATS level but lost at the HTTP level, requiring `ack_wait=300s` redelivery.

The batch fetch fix should eliminate this delay entirely.

## Task

Run integration test #4 to verify:
1. The batch fetch eliminates the ~5-minute idle time
2. End-to-end PSv2 flow still works (detection + classification + result posting)
3. Total time should be ~6 minutes or less (down from ~11)

## Steps

1. Make sure the `fix/nats-connection-safety` branch is checked out
2. Restart services to pick up code changes:
   ```bash
   docker compose restart django celeryworker celerybeat
   ```
3. Kill any stale ADC workers:
   ```bash
   pkill -f "ami worker" || true
   ```
4. Run the integration test:
   ```bash
   cd ~/Projects/AMI/ami-data-companion
   conda activate ami-py311
   bash ~/Projects/AMI/antenna/scripts/psv2_integration_test.sh 20
   ```
5. Monitor results — look for:
   - Tasks fetched quickly (no 5-min delay)
   - 20/20 images processed
   - Job status = SUCCESS

## ADC Setup Note

The ADC should be on the `fix/trailing-slashes` branch (committed `eac7481`) to avoid 301 redirects on `/tasks` and `/jobs` endpoints.

```bash
cd ~/Projects/AMI/ami-data-companion
git checkout fix/trailing-slashes
conda activate ami-py311
pip install -e .
```

## Remaining TODOs (from PR #1135)

After the test passes, these items remain for future work:

- [ ] NATS connection pooling (singleton per process instead of per-request)
- [ ] uvicorn `--workers 4` for dev config
- [ ] JetStream operation timeouts on `_ensure_stream()` / `_ensure_consumer()`
- [ ] `dispatch_mode` set at job creation instead of `run()`
- [ ] Multi-pipeline `/tasks` endpoint (workers request tasks for any pipeline they support)
- [ ] ADC pipeline params from `/info` endpoint
- [ ] GitHub #1122 — processing service online status
- [ ] GitHub #1112 — worker tracking in logs

## Key Files

- `ami/ml/orchestration/nats_queue.py` — `TaskQueueManager.reserve_tasks()` (batch fetch)
- `ami/jobs/views.py:217-255` — `/tasks` endpoint
- `ami/ml/orchestration/tests/test_nats_queue.py` — 9 unit tests (all passing)
- `scripts/psv2_integration_test.sh` — integration test script
- `docs/claude/sessions/2026-02-16-psv2-integration-test.md` — previous session findings
- `docs/claude/planning/nats-flooding-prevention.md` — full findings doc
