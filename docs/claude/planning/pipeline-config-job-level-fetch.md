# Proposal: move pipeline config from per-task to job-level fetch

**Status**: draft, not implemented. Tracks a follow-up to PRs #1279 (Antenna) + ADC #146.

## Context

After #1279, every `PipelineProcessingTask` published to NATS carries a `config` field. All tasks within a single job share the same config — ADC's `rest_collate_fn` already encodes this assumption with `successful[0].get("config")` — so embedding the config redundantly in every task is informationally wasteful and structurally incorrect.

This is fine for the current shape of pipeline configs (a handful of small primitives like `example_config_param: int`). It will not stay fine once configs grow to include things like:

- A taxa allow-list for a CLIP-style classifier (potentially thousands of names)
- Per-stage hyperparameter overrides
- Feature-flag toggles for "roll up taxa on the ADC side", `include_features`, `include_softmax`
- Per-job model variant selection or threshold curves

A job with N images and a config of size M ships N×M bytes through NATS today, when it should ship M bytes once.

## Proposed shape

### Pull mode (NATS)

Add a job metadata fetch that ADC calls **once per job**, before iterating tasks:

```
GET /api/v2/jobs/{job_id}/
```

Response includes (among existing fields) the resolved pipeline config:

```json
{
  "id": 7,
  "pipeline_slug": "global_moths_2024",
  "config": {
    "include_features": true,
    "taxa_allowlist": ["Lepidoptera", ...]
  },
  ...
}
```

ADC fetches and caches this once per job (already does `_fetch_tasks` per-job; add a sibling `_fetch_job_meta`). `PipelineProcessingTask.config` becomes vestigial and can be deprecated in a follow-up after both sides have shipped.

The existing `AntennaJobsListResponse` only returns `id` and `pipeline_slug`; this would be a separate detail endpoint, not a change to the list endpoint.

### Push mode (sync HTTP `POST /process`)

The push path is request/response, not task-fetched, so there's no equivalent "fetch once" moment for the worker. Two reasonable options:

1. **Keep config on each `PipelineRequest`** (status quo). Simple. Wastes bandwidth on the wire, but most push-mode requests are small (single image or a handful), so the overhead is bounded. No worker-side change.

2. **Send config in a job-init handshake**. The push API would need a notion of a "job" that workers can register against, which they don't have today — push-mode services are stateless w.r.t. jobs. Adding job state to push-mode workers is a substantially bigger change (cache invalidation, eviction, multi-tenant memory growth) and not worth it for the current config sizes.

Recommendation: **(1) for push, (2) for pull.** Push-mode requests are already independent — there's no "session" to attach config to without inventing one. Pull-mode has a natural job boundary already; reuse it.

## Migration

Pull mode:
1. Antenna ships a `GET /api/v2/jobs/{id}/` endpoint that includes `config` in the response.
2. ADC adds `_fetch_job_meta()` and reads `config` from there; falls back to `task.config` if the meta endpoint returns 404 (older Antenna).
3. After ADC ≥ this version is the floor, Antenna removes the per-task `config` field.

Push mode: no change.

## Costs of doing it now vs. later

Doing it now: bigger PR than #1279, but the schema isn't fossilized yet — only one consumer (ADC) and zero data persisted with the per-task shape.

Doing it later: every external worker that adopts the per-task `config` field becomes a backwards-compat constraint. The longer the per-task shape is "the contract," the more painful the migration.

The audit log added in this PR (`ami/jobs/tasks.py:process_nats_pipeline_result`) becomes simpler under job-level config: compare once at job start, not on every result.

## Out of scope

- Authentication / permissions on the new job meta endpoint (use whatever ADC already uses for `/tasks/`)
- Schema versioning of `config` itself (separate problem; matters more once configs start carrying user-editable structures like taxa lists)
- UI for editing `ProjectPipelineConfig` (already exists in admin; no change needed)
