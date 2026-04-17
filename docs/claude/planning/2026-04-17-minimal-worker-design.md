# Minimal worker (PSv2 pull-mode stub) — design

**Date:** 2026-04-17
**Status:** draft, initial stub
**Owner:** @mihow
**Related PRs:**
- RolnickLab/antenna#987 — job queue HTTP API (merged)
- RolnickLab/antenna#1194 — API key auth + `register.py` (open)
- RolnickLab/ami-data-companion#94 — ADC worker (merged)
- RolnickLab/ami-data-companion#136 — ADC API-key switch (open)

## Intention

Antenna supports two processing-service paradigms:

1. **Push / "v1" / interactive** — a FastAPI service exposes `/info`, `/livez`, `/readyz`, `/process`. Antenna POSTs `PipelineRequest` to `/process` when a job runs. Good for single-image inference-demo UIs, `/api/v2/docs/` schema exposure, and admin smoke tests. This is the only mode the existing `processing_services/minimal/` and `processing_services/example/` containers support today.

2. **Pull / "v2" / async / worker / consumer** — a long-running worker polls Antenna for work via the HTTP job-queue API (`POST /api/v2/jobs/{id}/tasks/`, `POST /api/v2/jobs/{id}/result/`) which Antenna proxies to a NATS JetStream queue. Workers can live behind firewalls, scale horizontally, run on GPUs without exposing any port. The only implementation today is the external [AMI Data Companion](https://github.com/RolnickLab/ami-data-companion) (ADC), which is heavyweight — conda environment, torch, real model weights, minutes of CUDA warmup.

**The gap.** E2E testing and dev iteration on the Redis/RabbitMQ/NATS/Celery/Celery-Beat lifecycle is bottlenecked by having to spin up the ADC to exercise the pull path. There is no stub for v2 analogous to what `minimal/` is for v1.

**The goal.** Add a minimal v2 worker stub that:

- Mimics the ADC's HTTP-only interaction with Antenna so agents and CI exercise the real API contract.
- Uses deterministic stub pipelines (no torch, no model weights, no GPU) so a fresh `docker compose up` reaches a job-processing state in seconds, not minutes.
- Runs headless with zero manual setup, correctly sequenced so GitHub CI can use it the same way a developer uses it locally.
- Leaves the v1 push path intact for interactive and schema-exposure use cases.

## Current state

### What exists

- `processing_services/minimal/` — v1 FastAPI stub. Two stub pipelines (`ConstantPipeline`, `RandomDetectionRandomSpeciesPipeline`). Used as the `ml_backend` service in `docker-compose.ci.yml` and alongside the main dev compose.
- `processing_services/example/` — v1 FastAPI with real zero-shot models. Intended as a template for real services.
- `ami/ml/schemas.py` — authoritative Pydantic schemas. v1 and v2 share `PipelineRequest` / `PipelineResultsResponse`. v2-specific: `PipelineProcessingTask`, `PipelineTaskResult`, `PipelineResultsError`, `ProcessingServiceClientInfo`.
- `ami/jobs/views.py::JobViewSet.tasks` (`POST /api/v2/jobs/{id}/tasks/`) — reserves a batch of tasks from NATS.
- `ami/jobs/views.py::JobViewSet.result` (`POST /api/v2/jobs/{id}/result/`) — accepts results, queues `process_nats_pipeline_result` Celery tasks.
- `ami/ml/views.py::ProjectPipelineViewSet.create` (`POST /api/v2/projects/{id}/pipelines/`) — registers pipelines for a pull-mode service. On main this expects `{"pipelines": [...], "processing_service_name": "..."}`. PR #1194 changes the auth and drops `processing_service_name` in favour of identification by API key.
- The ADC (external repo) is the only worker that exercises the pull path today.

### What is in flight

- **PR #1194** (Antenna): API-key auth for processing services, drops `processing_service_name` from pipeline registration, adds `client_info` to registration and tasks/result bodies, adds `processing_services/minimal/register.py` + `start.sh` for self-provisioning. Unmerged.
- **ADC PR #141**: Mothbot YOLO11m detector.
- **ADC PR #136**: switch ADC from user-token auth to API-key auth (companion to #1194).

This design **targets main** (unmerged PRs are not prerequisites). When #1194 lands, the worker stub is a small diff away from API-key auth — see "Forward compatibility" below.

## Desired state after this PR

- `docker compose up` (or `docker compose -f docker-compose.ci.yml up`) reaches a state where an `async_api` job submitted against the `constant` or `random-detection-random-species` pipeline is picked up and processed to completion **with zero manual steps**.
- The existing v1 push behavior of `minimal/` continues to work unchanged for CI tests that hit `/process`.
- Agents have a documented, code-first reference for the v2 API contract they can extend when adding new features.
- The pull path exercises Redis state updates, NATS ACK via `reply_subject`, Celery `process_nats_pipeline_result`, `pipeline.save_results`, and the stale-job cutoff — the same code paths the ADC exercises in production.

Out of scope:
- Real ML inference in the stub (stays random/constant).
- Renaming/rebuilding `example/` into `global_moths`/`complete` (follow-up).
- API-key-only auth (forward-compat, see below).
- Competing-consumer smoke tests, multi-worker tests, direct-NATS workers.

## Design

### Container architecture

One image (`processing_services/minimal/`) runs in one of three modes, selected by the `MODE` env var:

```
MODE=api         # FastAPI only (CI default; unchanged behavior)
MODE=worker      # poll loop only
MODE=api+worker  # FastAPI + register.py + poll loop (local dev default)
```

`start.sh` is the orchestrator. In `api+worker` it runs the FastAPI process in the background, runs `register.py` once (self-provisions a ProcessingService + registers pipelines), then starts the worker loop in the foreground. Signals propagate; if any child dies the container exits so the compose supervisor restarts it.

### Directory layout

```
processing_services/minimal/
├── Dockerfile               # base image + start.sh as CMD
├── start.sh                 # MODE-dispatching orchestrator
├── main.py                  # unchanged FastAPI entry
├── register.py              # self-provision + register pipelines (token-auth path now)
├── requirements.txt         # unchanged (requests + pydantic already present)
├── api/                     # unchanged v1 push-mode code
│   ├── api.py
│   ├── algorithms.py
│   ├── pipelines.py
│   ├── schemas.py
│   └── utils.py
├── worker/
│   ├── __init__.py
│   ├── client.py            # requests.Session wrapper for Antenna REST
│   ├── loop.py              # poll / reserve / process / submit loop
│   ├── runner.py            # turn one PipelineProcessingTask into a PipelineTaskResult
│   └── schemas.py           # local mirror of PipelineProcessingTask, PipelineTaskResult, etc.
└── worker_main.py           # entry used by MODE=worker and the third child in MODE=api+worker
```

`worker/runner.py` imports the existing `api/pipelines.py` and `api/algorithms.py` so stub detection/classification behavior is identical between v1 `/process` and v2 pull. No duplicated pipeline logic.

### Wire format

The worker speaks to Antenna over HTTP only. Direct NATS access from a worker is not supported (Antenna proxies NATS behind the HTTP endpoints). This matches the ADC contract and lets workers run behind firewalls.

**Fetch active jobs:**
- `GET /api/v2/jobs/?pipeline=<slug>&status=STARTED&ids_only=true` for each of the stub's pipeline slugs.

**Reserve tasks:**
- `POST /api/v2/jobs/{id}/tasks/` with `{"batch_size": 4}` →  `{"tasks": [PipelineProcessingTask, ...]}`

**Submit results:**
- `POST /api/v2/jobs/{id}/result/` with `{"results": [{"reply_subject": "...", "result": PipelineResultsResponse | PipelineResultsError}, ...]}`

All 3 endpoints use `Authorization: Token <token>` for now. See "Forward compatibility" for API-key migration.

### Poll loop (pseudocode)

```python
# Mode B: all-pipelines poll (this PR).
# TODO(follow-up): add `--pipeline <slug>` flag (mode A) for slug-filtered poll,
#   enables multiple workers as competing consumers for the same pipeline.
# TODO(follow-up): add `--job-id <id>` flag (mode C) for one-shot job-pinned runs,
#   for test harnesses that want to drain and exit.
my_slugs = list(pipeline_choices.keys())
while not shutdown:
    active_job_ids = client.list_active_jobs(pipelines=my_slugs)
    if not active_job_ids:
        sleep(WORKER_POLL_INTERVAL_SECONDS)
        continue
    for job_id in active_job_ids:
        tasks = client.reserve_tasks(job_id, batch_size=WORKER_BATCH_SIZE)
        if not tasks:
            continue
        results = [runner.process(task) for task in tasks]  # exceptions → PipelineResultsError
        client.submit_results(job_id, results)
```

Per-task errors are captured and posted as `PipelineResultsError` so the NATS ACK path still fires. That's important for exercising the retry / stale-job-cutoff / MaxRetriesExceeded paths (see CLAUDE.md on chaos testing).

### Automation and sequencing

`docker compose up` → worker loop polling actively in ~10s with no manual steps, despite the steps involved:

1. Postgres, RabbitMQ, Redis, NATS come up.
2. Django applies migrations.
3. **An idempotent `ensure_default_project` management command runs from the Django `/start` script when `ENSURE_DEFAULT_PROJECT=1` is set in the env.** It ensures:
    - The default user exists (`antenna@insectai.org`, password `localadmin`). Matches `.envs/.local/.django` and the values already baked into PR #1194's `register.py` defaults.
    - A project exists with a known slug (`default-project`). If one already exists with that slug, no-op. If not, create it with the default user as owner. The project's PK is looked up and exposed as the `ANTENNA_PROJECT_ID` env the minimal worker container reads.
4. The minimal container starts. `start.sh` launches FastAPI in background.
5. `register.py` waits for `http://localhost:2000/livez` (own server ready), then for `ANTENNA_API_URL/livez` (Antenna ready), then logs in, creates/finds a ProcessingService, registers pipelines. Has existing retry loop (10 attempts, 5s apart) for "project not found yet" etc.
6. `worker_main.py` starts polling.

The **alternative** I considered and rejected was handling (3) in the processing service itself (e.g. `register.py` creates the project if missing). Rejected because:
- A "worker" component shouldn't have project-creation privileges in any realistic deployment.
- Django `/start` is the natural place for bootstrap data — migrations already run there.
- Makes the same seed logic available to any other local/CI flow that doesn't involve a processing service.

The management command is gated by `ENSURE_DEFAULT_PROJECT=1` so it's opt-in. Set in `.envs/.local/.django` and `.envs/.ci/.django`, unset in `.envs/.production/*`.

### Env var contract

| Var | Default | Used by | Purpose |
|---|---|---|---|
| `MODE` | `api` (Dockerfile) / `api+worker` (dev compose) / `api` (CI compose) | `start.sh` | container entry mode |
| `ANTENNA_API_URL` | `http://django:8000` | register.py, worker | Antenna base URL |
| `ANTENNA_PROJECT_ID` | `1` | register.py, worker | project to register + poll under |
| `ANTENNA_USER` | `antenna@insectai.org` | register.py | local dev superuser |
| `ANTENNA_PASSWORD` | `localadmin` | register.py | local dev superuser password |
| `ANTENNA_API_AUTH_TOKEN` | unset | register.py, worker | if set, skip login and use this token directly |
| `ANTENNA_API_KEY` | unset | register.py, worker | TODO (PR #1194): if set, use `Api-Key <key>` auth |
| `ANTENNA_SERVICE_NAME` | `minimal-worker-{hostname}` | register.py | ProcessingService record name |
| `WORKER_POLL_INTERVAL_SECONDS` | `2.0` | worker | sleep when no active jobs |
| `WORKER_BATCH_SIZE` | `4` | worker | tasks per reserve call (matches ADC default) |
| `WORKER_REQUEST_TIMEOUT_SECONDS` | `30` | worker | per-HTTP-call timeout |
| `ENSURE_DEFAULT_PROJECT` | `1` in local/CI, unset elsewhere | Django `/start` | run idempotent seed command |

### Docker compose changes

**`processing_services/docker-compose.yml`** (local dev overlay):
- `ml_backend_minimal` gains `environment: MODE=api+worker, ANTENNA_API_URL, ANTENNA_PROJECT_ID, ANTENNA_USER, ANTENNA_PASSWORD`.
- `depends_on: django` (condition: `service_started`; the worker's register.py retries).

**`docker-compose.ci.yml`:**
- `ml_backend` keeps `MODE=api` (CI default, unchanged). Existing `/process`-based tests keep working.
- *(Deferred)* Optionally add `ml_backend_worker` as a second service entry under a compose profile for a future CI async test. Keeping CI behavior unchanged in this PR.

**Main `docker-compose.yml`** (Antenna stack):
- `django` service gets `ENSURE_DEFAULT_PROJECT=1` in its env (via `.envs/.local/.django`).

### Forward compatibility with PR #1194 (API-key auth)

`register.py` is written so the swap is small:

- It checks `ANTENNA_API_KEY` first → uses `Api-Key` auth.
- Otherwise uses `ANTENNA_API_AUTH_TOKEN` → uses `Token` auth.
- Otherwise logs in with `ANTENNA_USER` / `ANTENNA_PASSWORD` to get a token.

PR #1194 changes the request body (drops `processing_service_name`, adds `client_info`). We send both `processing_service_name` and a `client_info` dict now — the former is required by main, the latter is ignored by main (extra fields are allowed). When #1194 lands, a one-line change removes `processing_service_name` from the registration payload.

The worker's tasks/result endpoints already support token auth today and will support Api-Key after #1194; same conditional header-selection logic.

## Testing strategy

### What this PR verifies

- `docker compose -f processing_services/docker-compose.yml build ml_backend_minimal` succeeds.
- `MODE=api` container is backward-compatible with existing CI (same `/process` / `/info` / `/livez` / `/readyz`).
- `MODE=api+worker` container: in a full local stack, `curl` submits an `async_api` job for the `constant` pipeline, and the worker processes it to completion. `Job.status` reaches `SUCCESS`, `SourceImage.detections` populated, `Occurrence` rows created.
- `ensure_default_project` is idempotent: running twice is a no-op.

### What this PR does not verify

- API-key auth path (depends on PR #1194).
- Chaos-testing path (Redis/NATS fault injection) — the stub should work with those but it's a follow-up to wire into `scripts/psv2_integration_test.sh`.
- GitHub CI for an async path — current CI only exercises `/process`. Follow-up: add an async-job test that uses `MODE=worker`.

## Open questions and follow-ups

1. **Rename `example/` → `complete` / `global_moths`?** Deferred. The "example" service is already the "real one" — once we have the mothbot/foundation-model pipeline bundled, we rename. Not in this PR.
2. **Should `example/` also learn pull mode?** Yes, but as a second follow-up. The pattern established by the `worker/` subdirectory is directly reusable.
3. **`ANTENNA_DEFAULT_PROJECT_ID=1` conflicts:** Ensure command looks up by slug, not PK. PK 1 may already be claimed in long-lived dev DBs; we export whatever PK the seeded project actually has.
4. **Healthchecks for sequencing:** PR doesn't add Docker healthchecks for Django; register.py's retry loop is the sole mechanism for "wait for Antenna ready". Could add a healthcheck in a follow-up if retry noise becomes a problem.
5. **Worker heartbeat.** On main, ProcessingService.last_seen is updated only when the pipelines-registration endpoint is called. PR #1194 adds heartbeat-on-every-request via `_mark_pipeline_pull_services_seen` in `ami/jobs/views.py`. After #1194 lands, workers show up as "online" in the Antenna admin automatically.

## Links

- Antenna job queue API: `ami/jobs/views.py::JobViewSet.tasks`, `.result`
- Schemas: `ami/ml/schemas.py` (`PipelineProcessingTask`, `PipelineTaskResult`, `ProcessingServiceClientInfo`)
- Celery result handler: `ami/jobs/tasks.py::process_nats_pipeline_result`
- Async state manager: `ami/ml/orchestration/async_job_state.py`
- Task queue: `ami/ml/orchestration/nats_queue.py`
- ADC reference: https://github.com/RolnickLab/ami-data-companion/tree/main/trapdata/antenna
