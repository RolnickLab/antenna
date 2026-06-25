# Job Dispatch Modes

## Overview

The `Job` model is a user-facing CMS feature. Users configure jobs in the UI (selecting images, a processing pipeline, etc.), click start, and watch progress. The actual work is dispatched to background workers. The `dispatch_mode` field on `Job` describes *how* that work gets dispatched.

## The Three Dispatch Modes

### `internal`

All work happens within the platform itself. A Celery worker picks up the job and handles it directly — no external service calls.

**Job types using this mode:**
- `DataStorageSyncJob` — syncs files from S3 storage
- `SourceImageCollectionPopulateJob` — queries DB, populates a capture collection
- `DataExportJob` — generates export files
- `PostProcessingJob` — runs post-processing tasks

### `sync_api`

The Celery worker calls an external processing service API synchronously. It loops over items (e.g. batches of images), sends each batch to the processing service endpoint, waits for the response, saves results, and moves on.

**Job types using this mode:**
- `MLJob` (default path)

### `async_api`

The Celery worker publishes all items to a message broker (NATS). External processing service workers consume items independently and report results back. The job monitors progress and completes when all items are processed.

**Job types using this mode:**
- `MLJob` (when `project.feature_flags.async_pipeline_workers` is enabled)

## Architecture Context

```
User (UI)
  │
  ▼
Job (Django model) ─── dispatch_mode: internal | sync_api | async_api
  │
  ▼
Celery Worker
  │
  ├── internal ──────► Work done directly (DB queries, file ops, exports)
  │
  ├── sync_api ──────► HTTP calls to Processing Service API (request/response loop)
  │
  └── async_api ─────► Publish to NATS ──► External Processing Service workers
                                               │
                                               ▼
                                         Results reported back
```

## Naming Decisions

- **Why not `backend`?** Collides with Celery's "result backend" concept and the "ML backend" term used for processing services throughout the codebase.
- **Why not `task_backend`?** "Task backend" is specifically a Celery concept (where task results are stored).
- **Why not `local`?** Ambiguous with local development environments.
- **Why `internal`?** Clean contrast with the two external API modes. "Internal" means the work stays within the platform; `sync_api` and `async_api` both involve external processing services.
- **Why `dispatch_mode`?** The field describes *how* the Celery worker dispatches work to processing services, not how the job itself executes (all jobs execute via Celery). "Dispatch" is more precise than "execution" which is ambiguous.

## Code Locations

- Enum: `ami/jobs/models.py` — `JobDispatchMode`
- Field: `ami/jobs/models.py` — `Job.dispatch_mode`
- Serializer: `ami/jobs/serializers.py` — exposed in `JobListSerializer` and read-only
- API filter: `ami/jobs/views.py` — filterable via `?dispatch_mode=sync_api`
- Migration: `ami/jobs/migrations/0019_job_dispatch_mode.py`
- Tests: `ami/jobs/tests.py` — `TestJobDispatchModeFiltering`
