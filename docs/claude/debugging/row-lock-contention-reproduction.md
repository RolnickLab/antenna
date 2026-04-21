# Reproducing the `jobs_job` row-lock contention locally

Runbook for reproducing, on a local dev stack, the row-lock contention that
affects concurrent `async_api` ML jobs. Context: issue #1256, PR #1261, and
PR #1259 (complementary `JobLog` table refactor).

**Why this matters.** Naive repro attempts with a `curl` loop that fires one
result per POST (`{"results": [{...}]}`) do NOT trigger the pathology. They
only exercise the worker-side `select_for_update` path, which is fixed once
PR #1261 lands. The dominant remaining bottleneck is per-result logging
inside `ATOMIC_REQUESTS` — to see it locally you need **batched POSTs** that
match the real ADC shape (`AMI_LOCALIZATION_BATCH_SIZE=4`,
`AMI_CLASSIFICATION_BATCH_SIZE=150`).

## The pathology

Two mutating paths UPDATE the `jobs_job` row for every log line written via
`job.logger.info(...)`:

1. **View path** (`ami/jobs/views.py` — `result` and `tasks` actions): the
   per-iteration `job.logger.info("Queued pipeline result: ...")` inside the
   POST body loop runs under `ATOMIC_REQUESTS`. A single batched POST with N
   results therefore stacks N UPDATEs on `jobs_job.logs` inside one tx that
   doesn't commit until the view returns. Every other writer on the same row
   (other worker tasks, other POST handlers) blocks behind it.
2. **Worker path** (`ami/jobs/tasks.py` — `_update_job_progress`): each
   `process_nats_pipeline_result` celery task calls `_update_job_progress`,
   which emits its own log lines, each triggering another UPDATE on the same
   row.

The smoking gun in `pg_stat_activity`:

- Root blocker: a backend `state = idle in transaction`, last query
  `UPDATE "jobs_job" SET "logs" = ...`, held for many seconds.
- Waiters: dozens of backends with `wait_event_type = Lock`,
  `wait_event = tuple` or `transactionid`, all on the same row.

## Prereqs

- Local antenna stack up via the standard dev compose
  (`docker compose up -d`) with postgres, redis, rabbitmq, nats, django,
  celeryworker, and celeryworker_ml healthy.
- A job in a running state (any `async_api` job with `status = STARTED` will
  do — the view accepts results regardless of whether real tasks exist).
- An auth token for a user with permission to POST to
  `/api/v2/jobs/{id}/result/`.
- Python 3.10+ on the host (the load-test script uses stdlib only).

## Scripts

- `scripts/load_test_result_endpoint.py` — fires concurrent batched POSTs.
- `ami/jobs/management/commands/chaos_monkey.py` — adjacent tooling for
  `async_api` chaos scenarios; covered in `chaos-scenarios.md`.

## Step-by-step

### 1. Grab an auth token and a target job

From a shell on the host:

```bash
docker compose exec -T django python manage.py shell <<'PY'
from rest_framework.authtoken.models import Token
from ami.users.models import User
from ami.jobs.models import Job

u = User.objects.filter(is_staff=True).first()
t, _ = Token.objects.get_or_create(user=u)
print("TOKEN=", t.key)

j = Job.objects.filter(status="STARTED", dispatch_mode="async_api").first()
if j is None:
    # Any running job works — create one if there isn't one.
    # Adjust project/collection/pipeline PKs to your local data.
    print("No running async_api job found; create one via the UI or shell.")
else:
    print("JOB_ID=", j.pk)
PY
```

If no running job exists, create one with whatever project/collection/pipeline
are seeded locally. The view does not need real tasks queued behind the
job — it only needs the job row to accept result POSTs.

### 2. Fire batched POSTs

```bash
python scripts/load_test_result_endpoint.py <JOB_ID> <TOKEN> \
    --batch 50 --concurrency 10 --rounds 3
```

`--batch 50` puts 50 `PipelineResultsError` entries in each POST body. Any
batch size >1 will stack UPDATEs; 50 is a comfortable reproduction size
because it makes each POST's tx hold long enough for others to pile up.
`--concurrency 10` fires 10 parallel POSTs per wave. `--rounds 3` fires
three back-to-back waves.

### 3. Monitor Postgres during the test

In a second shell:

```bash
docker exec <postgres-container> psql -U <user> -d <db> <<'SQL'
-- Scalars
SELECT count(*) AS idle_in_tx
  FROM pg_stat_activity
 WHERE datname = current_database() AND state = 'idle in transaction';

SELECT count(*) AS blocker_chain
  FROM pg_stat_activity blocked
  JOIN pg_stat_activity blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
 WHERE blocked.wait_event_type = 'Lock'
   AND blocked.datname = current_database();

-- Top offenders
SELECT state, wait_event,
       substring(query, 1, 80),
       EXTRACT(EPOCH FROM now() - xact_start) AS xact_age_s
  FROM pg_stat_activity
 WHERE datname = current_database()
   AND state != 'idle'
   AND (state = 'idle in transaction' OR wait_event_type = 'Lock')
 ORDER BY xact_start NULLS LAST
 LIMIT 20;
SQL
```

### 4. Before/after signatures

Measured on a local dev stack with WEB_CONCURRENCY=1 (gunicorn default) and
8 celery ML-fork workers, batch=50, concurrency=10.

| Signal | PR #1261 only (`JOB_LOG_PERSIST_ENABLED=true`) | PR #1261 + flag off (`JOB_LOG_PERSIST_ENABLED=false`) |
|---|---|---|
| `blocker_chain` count | 30+ | 0–1 (transient) |
| `idle_in_tx` count | 8–10 | 0 |
| Root-blocker query | `UPDATE jobs_job SET logs = ...` held 2–60s | transient `SELECT`s only |
| POST success (10 concurrent × 50-result batch, 120s timeout) | 0/10 (all timeout) | 10/10 |
| p95 POST latency | 120s+ | ~5s |

## The feature flag

Setting `JOB_LOG_PERSIST_ENABLED=false` (env var on the Django container)
causes `JobLogHandler.emit` to write only to the container stdout logger and
skip the per-record UPDATE on `jobs_job.logs`. The per-job UI log feed
stops receiving new entries while the flag is off; container stdout still
captures everything.

Default is `true` — existing deployments keep their current behavior. The
flag is intended as a time-bounded escape hatch until the append-only
`JobLog` child table from PR #1259 is in place.

To test the flag locally, append `JOB_LOG_PERSIST_ENABLED=false` to the
django env file used by your compose (e.g. `.envs/.local/.django`) and
recreate the django container (`docker compose up -d --force-recreate
django`). Verify from a shell:

```bash
docker compose exec -T django python -c \
  "from django.conf import settings; print(settings.JOB_LOG_PERSIST_ENABLED)"
```

## Related

- Issue #1256 — full contention analysis with path breakdown.
- PR #1261 — drops `select_for_update` in `_update_job_progress`; adds the
  `JOB_LOG_PERSIST_ENABLED` flag; this runbook.
- PR #1259 — append-only `JobLog` child table. When merged, the flag can be
  removed in favor of a cutover to the new write path.
- `docs/claude/debugging/chaos-scenarios.md` — adjacent chaos tooling for
  NATS redelivery and retry-path validation.
