# Monitoring Async (NATS) Jobs

Reference for monitoring and debugging async_api jobs that use NATS JetStream for task distribution to external workers (e.g., AMI Data Companion).

## Starting a Test Job

```bash
docker compose run --rm django python manage.py test_ml_job_e2e \
  --project 18 \
  --dispatch-mode async_api \
  --collection 142 \
  --pipeline "global_moths_2024"
```

Or create a job via the UI at http://localhost:4000/projects/18/jobs.

## Monitoring Points

### 1. Web UI

**Job details page:** `http://localhost:4000/projects/{PROJECT_ID}/jobs/{JOB_ID}`

Shows status bar, progress percentage, stage breakdown, and logs. Polls the API automatically.

### 2. Jobs REST API

```bash
# Get auth token
TOKEN=$(docker compose exec django python manage.py shell -c \
  "from rest_framework.authtoken.models import Token; print(Token.objects.first().key)" 2>/dev/null)

# Job status & progress summary
curl -s http://localhost:8000/api/v2/jobs/{JOB_ID}/ \
  -H "Authorization: Token $TOKEN" | jq '{id, status, dispatch_mode, progress: .progress.summary}'

# Full stage breakdown
curl -s http://localhost:8000/api/v2/jobs/{JOB_ID}/ \
  -H "Authorization: Token $TOKEN" | jq '.progress.stages[] | {key: .key, status: .status, progress: .progress}'
```

### 3. Tasks Endpoint (Worker-Facing)

This is what the external worker polls to get batches of images to process.

```bash
# See what the worker would get (fetches from NATS, reserves tasks)
curl -s "http://localhost:8000/api/v2/jobs/{JOB_ID}/tasks/?batch=8" \
  -H "Authorization: Token $TOKEN" | jq '.tasks | length'

# Returns empty [] when job is not in active_states (STARTED, RETRY)
# i.e. returns empty for CANCELING, REVOKED, SUCCESS, FAILURE, etc.
```

### 4. Django ORM (Shell)

```bash
docker compose exec django python manage.py shell -c "
from ami.jobs.models import Job
j = Job.objects.get(pk={JOB_ID})
print(f'Status: {j.status}')
print(f'Dispatch mode: {j.dispatch_mode}')
print(f'Progress: {j.progress.summary.progress*100:.1f}%')
print(f'Started: {j.started_at}')
print(f'Finished: {j.finished_at}')
for s in j.progress.stages:
    print(f'  {s.key}: {s.status} {s.progress*100:.1f}%')
"
```

### 5. NATS JetStream Consumer State

Shows the queue depth, in-flight tasks, and acknowledgment progress.

```bash
docker compose exec django python manage.py shell -c "
from ami.ml.orchestration.nats_queue import TaskQueueManager
import asyncio
async def check():
    async with TaskQueueManager() as m:
        info = await m.js.consumer_info('job_{JOB_ID}', 'job-{JOB_ID}-consumer')
        print(f'num_pending:      {info.num_pending}')      # Tasks waiting in queue
        print(f'num_ack_pending:  {info.num_ack_pending}')   # Tasks reserved but not yet ACKed
        print(f'num_redelivered:  {info.num_redelivered}')   # Tasks redelivered after timeout
        print(f'delivered.seq:    {info.delivered.stream_seq}')  # Last delivered sequence
        print(f'ack_floor.seq:    {info.ack_floor.stream_seq}') # Last contiguous ACK
asyncio.run(check())
"
```

Key fields:
- `num_pending` = tasks still in queue, not yet reserved by any worker
- `num_ack_pending` = tasks reserved by worker, waiting for result POST + ACK
- `num_redelivered` = tasks that timed out (TTR=30s default) and were redelivered
- When `num_pending=0` and `num_ack_pending=0`, all tasks have been processed

### 6. Redis State (Atomic Progress Counters)

Tracks per-stage progress independently of the Job model. Updated atomically by Celery result tasks.

```bash
docker compose exec django python manage.py shell -c "
from ami.ml.orchestration.async_job_state import AsyncJobStateManager
sm = AsyncJobStateManager({JOB_ID})
for stage in sm.STAGES:
    prog = sm.get_progress(stage)
    print(f'{stage}: remaining={prog.remaining} processed={prog.processed}/{prog.total} failed={prog.failed} ({prog.percentage*100:.1f}%)')
"
```

### 7. Django Logs (Docker Compose)

```bash
# All django logs (includes task reservations and result processing)
docker compose logs -f django

# Filter for specific job
docker compose logs -f django 2>&1 | grep "1408"

# Filter for task reservations
docker compose logs -f django 2>&1 | grep "Reserved"

# Filter for result processing
docker compose logs -f django 2>&1 | grep "Queued pipeline result"
```

### 8. Celery Worker Logs

```bash
# Celery worker logs (result saving, NATS ACKs, progress updates)
docker compose logs -f celeryworker

# Filter for specific job
docker compose logs -f celeryworker 2>&1 | grep "job 1408"
```

### 9. AMI Worker Logs (External)

The AMI Data Companion worker runs outside Docker. Check its terminal output for:
- Batch processing progress (e.g., "Finished batch 84. Total items: 672")
- Model inference times (detection + classification)
- Connection errors to Django API or NATS

```bash
# If running via conda
conda activate ami-py311
ami worker --pipeline global_moths_2024

# Worker registration (loads ML models, ~20s)
ami worker register "local-worker" --project 18
```

## Continuous Monitoring (Watch Loop)

```bash
# Poll job status every 5 seconds
watch -n 5 'docker compose exec django python manage.py shell -c "
from ami.jobs.models import Job
j = Job.objects.get(pk={JOB_ID})
print(f\"Status: {j.status} | Progress: {j.progress.summary.progress*100:.1f}%\")
for s in j.progress.stages:
    print(f\"  {s.key}: {s.status} {s.progress*100:.1f}%\")
"'
```

## Job Lifecycle (async_api)

```text
CREATED → PENDING → STARTED → [processing] → SUCCESS
                        ↓
                    CANCELING → REVOKED  (user cancels)
                        ↓
                     FAILURE  (error during processing)
```

1. **STARTED**: Celery task collects images, publishes to NATS stream, then returns
2. **Processing**: Worker polls `/tasks`, processes batches, POSTs to `/result/`
3. **SUCCESS**: All results received, progress reaches 100%
4. **CANCELING → REVOKED**: User cancels, NATS stream/consumer deleted, status set to REVOKED. In-flight results may still trickle in and are saved.

## Key Configuration

| Setting | Default | Source |
|---------|---------|--------|
| NATS task TTR (visibility timeout) | 30s | `NATS_TASK_TTR` env var |
| NATS max_ack_pending | 1000 | `NATS_MAX_ACK_PENDING` env var |
| NATS max_deliver (retries) | 5 | hardcoded in `nats_queue.py` |
| NATS stream retention | 24h | hardcoded in `nats_queue.py` |
| Worker batch size | varies | worker's `?batch=N` param |

## Troubleshooting

**Job stuck in STARTED with no progress:**
- Check if worker is running and connected
- Check NATS consumer state — if `num_pending > 0` but nothing is being delivered, worker may have lost connection
- Check `num_redelivered` — high count means tasks are timing out (worker too slow or crashing)

**Job stuck in CANCELING:**
- Pre-fix: job was stuck because `/tasks` kept serving tasks and nothing transitioned to REVOKED
- Post-fix: `cancel()` cleans up NATS resources and sets REVOKED synchronously
- If still stuck, the periodic `check_incomplete_jobs` beat task (PR #1025) will catch it

**Results not being saved:**
- Check celeryworker logs for errors in `process_nats_pipeline_result`
- Check Redis state — if `process` is ahead of `results`, Celery is backed up saving results
- Check NATS `num_ack_pending` — high count means results haven't been ACKed yet
