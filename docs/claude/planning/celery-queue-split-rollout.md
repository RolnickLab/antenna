# Celery queue split — rollout plan

Branch: `feat/celery-queue-split` (commit `f772045b`). Opened against `main`.

## What the change does

Splits Celery tasks across three RabbitMQ queues, each consumed by a
dedicated worker service, so one class of task cannot starve another:

| Queue        | Tasks                                                                       | Rationale                                           |
| ------------ | --------------------------------------------------------------------------- | --------------------------------------------------- |
| `antenna`    | default — beat, cache refresh, sync, misc                                   | Fast, high-turnover housekeeping                    |
| `jobs`       | `run_job`                                                                   | Can hold a worker slot for hours                    |
| `ml_results` | `process_nats_pipeline_result`, `save_results`, `create_detection_images`   | Bursty, ~180 tasks / 5 min per active async_api job |

Worker start script is parameterized via `CELERY_QUEUES` env var (default
`antenna`), so one image serves all three services.

**Topology (production):**

- `ami-live` runs only the `antenna` worker (alongside Django + beat + flower).
  Heavy bursty work is kept off the app host.
- Dedicated worker hosts (`ami-worker-2`, `ami-worker-3`) run all three
  services via `docker-compose.worker.yml`. Each queue has its own container
  on each worker host so a burst on one class cannot saturate the pool and
  starve another.

## Why this is needed (motivating incident)

On a demo async_api job of ~740 images, `run_job` invocations for newly
submitted jobs sat in PENDING for many minutes behind the flood of
`process_nats_pipeline_result` tasks the first job was emitting. With
`prefetch_multiplier=1` and concurrency=8, the single worker's slot pool
was saturated by ML result processing. Splitting gives each class its own
pool. See issue #1256 for the related JobLog write-path bug this
investigation surfaced.

## Test plan on the demo environment

Goal: validate on demo **without** merging to `main` or running the
standard deploy flow. Files are scp'd directly onto the demo host; the
repo is left in a known dirty state that a subsequent `reset_to_branch.sh`
will cleanly nuke.

### Pre-flight (confirm clean window)

1. Confirm RabbitMQ `antenna` queue at 0 messages
2. Confirm NATS streams at 0 pending
3. Confirm no active jobs in the demo DB (`status not in SUCCESS/FAILURE/REVOKED/CANCELED`)

### Apply changes on demo (no push, no reset script)

1. scp the three changed files onto the demo host:
   - `config/settings/base.py`
   - `compose/production/django/celery/worker/start`
   - `docker-compose.staging.yml` (demo uses the staging compose file)
2. Rebuild the django image locally on demo:
   `docker compose -f docker-compose.staging.yml --env-file .envs/.production/.compose build django`
3. Force-recreate all services using that image:
   `docker compose ... up -d --force-recreate`
   (django, celerybeat, flower, celeryworker, celeryworker_jobs, celeryworker_ml)

### Post-deploy verification

- `docker compose ... ps` shows 3 celeryworker containers running
- `rabbitmqctl list_queues name messages consumers` shows three queues
  (`antenna`, `jobs`, `ml_results`), each with exactly 1 consumer
- Trigger a small `run_job` (e.g. a 5-image collection):
  - Task lands on `jobs` queue (visible in Flower / `list_queues`)
  - Starts within seconds
- Trigger an async_api job (~50 images) and watch:
  - `ml_results` queue fills, drains on its own worker
  - `antenna` queue stays at ~0, beat tasks still firing on time
  - A second `run_job` submitted mid-flight starts immediately (not blocked)

### Rollback

`~/reset_demo_to_branch.sh main` restores the deployment branch to `main`,
wiping our scp'd changes. Demo goes back to single-worker config within
a few minutes.

## Path to production (after demo validates)

1. Open PR `feat/celery-queue-split` → `main`
2. Code review (queue routing is a system-level change; at least one
   reviewer familiar with the Celery topology)
3. Merge to `main`
4. Production deploy must update the celery-consuming hosts in this order
   to avoid unrouted tasks piling up on an unread queue:
   - First: worker-only hosts (now run three dedicated services — `antenna`,
     `jobs`, `ml_results`)
   - Second: ami-live (now runs only the `antenna` worker; the previous
     single-queue worker is reconfigured to the `antenna` queue only)
5. Post-deploy: same queue / consumer verification as on demo, but counting
   consumers across both worker hosts (e.g. `jobs` queue should show 2
   consumers = one per worker host)

## Things that could go wrong and how we'd notice

- **Image rebuild fails on demo** — unlikely (change is text-only), but
  would leave the old container running with the old settings. Visible
  via `docker compose ps`.
- **A new queue has zero consumers** — tasks pile up silently. Caught by
  the "three queues, one consumer each" check above.
- **Django publisher reads stale routes** — the settings change is read
  at process start; django container must be recreated alongside the
  workers (step 3 above handles this).
- **Beat scheduler uses wrong queue for a scheduled task** — only an
  issue if a beat task name happens to match a `CELERY_TASK_ROUTES` key.
  Currently routed tasks (`run_job`, `process_nats_pipeline_result`,
  `save_results`, `create_detection_images`) are not in the beat schedule,
  so this shouldn't happen.
- **Worker VM memory pressure** — splitting the previous single-container
  worker into three doubles the baseline prefork process count on each VM
  (3 × `CELERY_WORKER_CONCURRENCY`). Watch RSS after deploy; if memory is
  tight, lower `CELERY_WORKER_CONCURRENCY` in the worker host `.env`.

## Related

- #1256 — JobLogHandler.emit write-path (the symptom that triggered this
  investigation)
- #1026 — concurrent job log updates, complementary to this change
