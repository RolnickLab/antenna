# Jobs panel: pick a job type, configure it from its schema — Design

**Status:** proposal, not yet approved
**Date:** 2026-09-18
**Supersedes the "future work" section of:** `docs/claude/planning/2026-05-01-post-processing-admin-scaffolding-design.md`
**Related:** #954 (closed, post-processing framework), #1289 (closed, admin scaffolding), #999 (closed, class masking), #1368 (closed, re-runnable masking), #1377 + #1404 (open, class masking fixes), #1272 (open, tracking), #1361 (open, rank rollup), #1369 (open, capture-set sampling args 500)

## Goal

One Create Job panel where an operator picks **what kind of job to run** — an ML pipeline or a
post-processing method — and then fills in **that job's own configuration**, with the form fields
generated from the Pydantic schema that already validates the config on the server. Adding a new
post-processing task, or a new knob on an existing one, should require no frontend change.

Non-goals for this design: replacing the Django admin trigger (it keeps working, on the same
schemas), scheduling/recurring jobs, and editing a job's config after creation.

---

## 1. Where we are today

### 1.1 The Create Job form is one hardcoded ML form

`ui/src/pages/job-details/new-job-dialog.tsx` → `job-details-form/job-details-form.tsx` renders five
fixed controls: name, delay, capture set (`CaptureSetPicker`), pipeline (`EntityPicker`), and a
"Start immediately" checkbox. `useCreateJob.ts` maps exactly those five names onto
`project_id` / `pipeline_id` / `source_image_collection_id` / `source_image_single_id` / `delay`, and
posts to `/jobs/` with an optional `?start_now`.

There is no job-type selector anywhere in the UI. Every job created from the panel is an ML job.

### 1.2 The API has seven job types, and the panel can only express one

`VALID_JOB_TYPES` (`ami/jobs/models.py:980`) holds `MLJob`, `SourceImageCollectionPopulateJob`,
`DataStorageSyncJob`, `RegroupEventsJob`, `DataExportJob`, `PostProcessingJob`, `UnknownJobType`.

`JobListSerializer` accepts `job_type_key` as a write-only field defaulting to `MLJob.key`, with the
comment *"@TODO Remove this when the UI is updated pass a job type. This should be a required
field."* (`ami/jobs/serializers.py:56`).

Two gaps follow from that:

- **No discovery endpoint.** Nothing serves the list of job types, what each one needs, or whether
  the current user may run it. `job_type` appears on responses only as `{name, key}` and as a
  filter. A client cannot learn that `post_processing` exists, let alone what to send with it.
- **`params` is not writable.** `Job.params` (JSONField, `ami/jobs/models.py:1050`) is absent from
  the serializer's field list entirely. It is where post-processing config lives, so the one job
  type that is fully configurable is the one the API cannot configure.

### 1.3 Post-processing already has the schema contract — only the admin can reach it

`BasePostProcessingTask` (`ami/ml/post_processing/base.py`) requires each task to declare
`key`, `name`, and `config_schema: type[pydantic.BaseModel]`, and validates config at construction.
Jobs are created as `params={"task": <key>, "config": {...}}` (`ami/ml/post_processing/admin/actions.py:131`).

Tasks on main: `small_size_filter`, `class_masking`. In flight: `rank_rollup` (#1361),
`tracking` (#1272). The registry (`ami/ml/post_processing/registry.py`) is the single source of truth
for which tasks exist.

The only trigger is `make_post_processing_action`, a Django admin action: select rows → confirmation
page → validate each row's config against the task schema → enqueue one Job per row. Good machinery,
reachable by superusers only.

### 1.4 Every task's knobs are written twice, and the copies drift

The schema is the source of truth for validation; a hand-written Django form is the source of truth
for labels, help text and widgets. Four tasks, four form files, and the duplication is already
costing us:

| Task | Schema | Form | Drift |
|---|---|---|---|
| `small_size_filter` | `SmallSizeFilterConfig` | `small_size_filter_form.py` | Form re-declares the default by reaching into `__fields__`; the `0 < x < 1` rule lives only in the validator, so the form accepts `5` and the server rejects it |
| `class_masking` | `ClassMaskingConfig` | `class_masking_form.py` | #1377 adds a knob and has to edit both files |
| `rank_rollup` (#1361) | `RankRollupConfig` | `rank_rollup_form.py` | Form is **empty** — `thresholds: dict[str, float]` and `rollup_order: list[str]` have no Django widget, so the operator cannot set them at all |
| `tracking` (#1272) | `TrackingConfig` | `admin/tracking_form.py` **and** `admin_forms.py` | Two `TrackingActionForm` classes in the same PR, with different fields (`require_features` vs `require_fresh_event` phrasing, different help text) |

The rank-rollup row is the important one: hand-written Django forms cannot express the config shapes
tasks actually use, so a knob that exists in the schema silently becomes unreachable.

### 1.5 We have already shipped this failure mode once

Capture-set sampling is the precedent. `SourceImageCollection.method` + `kwargs` dispatch to
`sample_*` methods whose kwargs are plain Python signatures — nothing publishes them. So
`ui/src/pages/project/entities/details-form/capture-set-details-form.tsx` hardcodes the *union* of
every method's kwargs (ten fields), `SERVER_SAMPLING_METHODS` hardcodes which three methods the UI
admits, and the form filters fields per method inline. PR #1369 ("Don't 500 when extra args passed to
sampling methods from UI") exists because that union leaks arguments a method does not take.

A second hardcoded config form for jobs would reproduce this, against a registry that grows faster.

### 1.6 Pipeline config is project-wide, never per job

`Pipeline.get_config(project_id)` merges `Pipeline.default_config` with
`ProjectPipelineConfig.config` (`ami/ml/models/pipeline.py:1236`). Both ML dispatch paths call it —
`MLJob.process_images` (`ami/jobs/models.py:574`) for the batch size, and `process_images()`
(`ami/ml/models/pipeline.py:316`) for the request config. **Neither reads `job.params`**: an ML job
cannot carry its own config today, even via the API.

What the API publishes about a pipeline's config is not enough to build a form either:
`PipelineSerializer` exposes `stages[]` (`PipelineStage.params[]` = `name` / `key` / `category`, with
no type, default, or value) and `project_pipeline_configs[].config` as a raw JSON blob.

One piece of the answer is already written: **#1272 converts `PipelineRequestConfigParameters` from a
bare `dict` subclass into a Pydantic model** with three declared, described fields
(`include_features`, `request_source_image_batch_size`, `reprocess_existing_detections`) and
`extra = "allow"`. That is the ML equivalent of a task's `config_schema`.

### 1.7 Permissions are ready except for the grant

`Job.get_custom_user_permissions` parses project permissions of the form `{action}_{job_type_key}_job`
(`ami/jobs/models.py:1400`), and `perform_create` enqueues only if `check_custom_permission(user, "run")`
passes. `Project.Permissions.RUN_POST_PROCESSING_JOB = "run_post_processing_job"` exists
(`ami/main/models.py:454`) and is in the project's `Meta.permissions`, but **no role in
`ami/users/roles.py` is granted it** — `MLDataManager` gets `run_ml_job`,
`run_populate_captures_collection_job`, `run_data_storage_sync_job`, `run_regroup_events_job`,
`run_data_export_job`, and not this one. So even with an API, post-processing stays superuser-only
until a role grant lands.

### 1.8 What the earlier design deliberately deferred

The merged scaffolding design listed as out of scope: *"REST API surface for triggering
post-processing from UI"* and *"Schema-driven form generation … Tempting but premature; current task
count = 1, second adopter has scope-aware dropdowns that don't fit auto-generation."*

Both conditions have changed. Task count is 4. And the scope-aware dropdown problem has a concrete
answer now — see §3.2.

---

## 2. Verified schema behaviour (Pydantic v1)

The container pins `pydantic<2` (`requirements/base.txt:17`, held there by `django-pydantic-field`).
I ran `.schema()` against copies of the four task configs and #1272's
`PipelineRequestConfigParameters` under pydantic 1.10.26 (script:
scratchpad `schema_probe.py` / `schema_probe2.py`; not committed). Measured results:

1. **Titles are auto-generated from field names.** `source_image_collection_id` →
   `"Source Image Collection Id"`. Every task's real documentation currently lives in Python
   comments above the field, which never reach the schema. Migrating those comments to
   `Field(title=..., description=...)` is a prerequisite, not a nice-to-have.
2. **Validators are invisible.** `SmallSizeFilterConfig.size_threshold` emits no `minimum`/`maximum`
   — its `0 < x < 1` rule is a `@validator`. `ClassMaskingConfig`'s `_exactly_one_scope`
   root validator has no representation at all. Declared as `Field(gt=0, lt=1)` the same rule emits
   `exclusiveMinimum` / `exclusiveMaximum` and becomes client-checkable.
3. **`Optional[int] = None` emits `{"type": "integer"}` and stays out of `required`** — no
   `anyOf`/`null` noise to normalize in v1.
4. **`Config.extra` is visible in the output.** `extra = "forbid"` emits
   `"additionalProperties": false`; `extra = "allow"` (the pipeline config) omits it. The client can
   read that to decide whether to offer a free-form advanced key/value editor.
5. **Arbitrary `Field(...)` kwargs pass straight through into the property.**
   `Field(..., ami_widget="entity", ami_entity="algorithms", ami_entity_filters={...})` appears
   verbatim in the JSON Schema. This is the mechanism for widget hints — no parallel `ui_schema`
   file to keep in sync.
6. **Enums arrive as `allOf: [{$ref}]` plus a `definitions` block**, and `list[Enum]` as
   `items: {$ref}`. The client should never resolve refs; the server normalizes (§3.3).
7. `dict[str, float]` → `{"type": "object", "additionalProperties": {"type": "number"}}`;
   `list[int]` → `{"type": "array", "items": {"type": "integer"}}`. Both are renderable — which is
   what makes rank rollup's unreachable knobs reachable.

---

## 3. Design

### 3.1 One descriptor per job type, served by one endpoint

`GET /api/v2/jobs/types/?project_id=<id>` returns everything the panel needs to render itself:

```jsonc
{
  "results": [
    {
      "key": "ml",
      "name": "ML pipeline",
      "description": "Run a processing pipeline over a set of captures.",
      "permission": "run_ml_job",
      "allowed": true,                       // resolved for the requesting user on this project
      "scope": [                             // maps onto Job's FK columns (§3.4)
        {"field": "pipeline_id", "widget": "entity", "entity": "pipelines",
         "required": true, "label": "Pipeline"},
        {"field": "source_image_collection_id", "widget": "capture_set",
         "required": true, "label": "Capture set"}
      ],
      "config_schema": { /* PipelineRequestConfigParameters, normalized */ },
      "config_defaults": { /* resolved project-level values, §3.6 */ }
    },
    {
      "key": "post_processing",
      "name": "Post processing",
      "permission": "run_post_processing_job",
      "allowed": false,
      "variant_key": "task",                 // where the choice is written in params
      "variants": [
        {"key": "class_masking", "name": "Class masking",
         "description": "Re-score a classifier's predictions against a taxa list.",
         "scope": [ /* … */ ],
         "config_schema": { /* ClassMaskingConfig, normalized */ }}
      ]
    }
  ]
}
```

Rules the endpoint follows:

- Job types the UI must never offer (`unknown`, and anything a job type marks
  `user_creatable = False`) are omitted. `data_storage_sync`, `populate_captures_collection` and
  `regroup_events` are created from their own pages today; they are listed with their scope so the
  panel *can* offer them, behind the same permission gate.
- `allowed` is computed from the same `run_{key}_job` permission `perform_create` enforces — the UI
  disables rather than hides, so an operator can see a capability exists and ask for the role.
- Variants come from the existing registries: `POSTPROCESSING_TASKS` for post-processing,
  `ExportRegistry` for `data_export` if we choose to fold exports in (see §6, open question 3).

### 3.2 Widget hints live on the Pydantic field

The blocker the earlier design named — "scope-aware dropdowns don't fit auto-generation" — is
solved by annotating the field rather than hand-writing a form:

```python
class ClassMaskingConfig(pydantic.BaseModel):
    algorithm_id: int = pydantic.Field(
        ...,
        title="Source classifier",
        description="The classification algorithm whose terminal predictions will be re-scored.",
        ami_widget="entity",
        ami_entity="algorithms",
        ami_entity_filters={"task_type": "classification"},
    )
    taxa_list_id: int = pydantic.Field(
        ..., title="Taxa list to keep", ami_widget="entity", ami_entity="taxa_lists",
    )
    reweight: bool = pydantic.Field(True, title="Reweight scores", description="…")
```

A thin `ami_field()` wrapper can supply the `ami_*` keys with typed arguments so tasks are not
writing bare strings, but the transport is just `Field` extras (measured: §2 item 5).

**The server sends a filtered endpoint, never the options themselves.** The UI calls
`/api/v2/algorithms/?project=<id>&task_type=classification` through the existing `EntityPicker`,
which paginates and searches. This matters: `class_masking_form.py` already carries a comment
explaining that narrowing the classifier dropdown by an unbounded `DISTINCT` over a collection's
classifications "can time out while the form renders" — a list endpoint with a filter and a page size
does not have that failure mode, and no new N+1 is introduced into form rendering.

### 3.3 The server normalizes the schema; the client renders a fixed subset

`config_schema` in the response is `Model.schema()` put through a normalizer that:

- inlines `$ref`/`definitions` and collapses single-element `allOf` (so enums arrive as
  `{"type": "string", "enum": [...]}` inline);
- fills a `title` for any field that lacks one (never the auto-generated
  `"Source Image Collection Id"` — fall back to sentence-cased field name);
- strips fields the panel supplies itself (the scope ids listed in `scope`), so they cannot be
  rendered twice;
- adds `"x-ami-schema-version": 1` so a later Pydantic v2 migration (`$defs`, `anyOf` for optionals)
  can change the producer without breaking a deployed client.

The client renderer (`SchemaForm`) supports exactly: `string` (+ `enum` → Select, `pattern`),
`integer` / `number` (+ `minimum` / `maximum` / `exclusiveMinimum` / `exclusiveMaximum` → RHF rules),
`boolean` → Checkbox, `array` of scalar or enum → multi-select or the existing integer-list helpers
(`parseIntegerList` / `formatIntegerList` / `validateIntegerList` in `utils/fieldProcessors`),
`object` with `additionalProperties` → key/value rows (this is what makes rank rollup's `thresholds`
editable), and any property carrying `ami_widget` → the mapped picker.

**Anything unsupported falls back to a JSON textarea** validated on submit by the server. A new task
is then never *unusable* from the UI — worst case it is inelegant, which is the property that lets us
ship the panel before every schema is annotated.

### 3.4 Scope stays on the Job columns; config stays in `params`

Today scope lives in two places: FK columns on `Job` (`source_image_collection`, `deployment`,
`source_image_single`, `pipeline`) for ML-family jobs, and inside `params["config"]`
(`source_image_collection_id`, `occurrence_id`, `event_ids`) for post-processing.

**Keep both, and make the panel responsible for the mapping.** The FK columns power the jobs list
filters (`JobFilterSet`), the Job detail page, and `related_name` joins; moving scope into a JSON blob
would lose all of that. So:

- The descriptor's `scope[]` names serializer fields (`source_image_collection_id`, …). The panel
  writes those at the top level of the POST body.
- For job types whose task schema also wants the scope (all post-processing tasks), the serializer
  **copies** the resolved scope ids into `params["config"]` before validation. One direction only,
  server-side, so the admin path and the API path produce byte-identical `params`.
- `_exactly_one_scope` root validators keep working unchanged, and keep being the authority.

### 3.5 `params` becomes writable, validated by the job type

Add a `JobCreateSerializer` (subclassing today's serializer) that accepts `params` on create only and:

1. resolves the job type from `job_type_key` (now required — closing the `@TODO` at
   `serializers.py:56`, with the current default kept for one release for the two existing callers);
2. resolves the variant from `params[job_type.variant_key]` when the type has variants;
3. merges scope (§3.4) and validates `params["config"]` against the Pydantic schema;
4. maps `pydantic.ValidationError` onto DRF field errors so the panel can show them inline —
   `ami/ml/post_processing/admin/actions.py:69` (`_schema_errors_to_form_fields`) already does this
   mapping for admin forms and should be lifted to a shared helper rather than written twice.

To keep this from becoming a chain of `if key == ...`, the contract moves onto `JobType`:

```python
class JobType:
    key: str
    name: str
    description: str = ""
    user_creatable: bool = True
    required_permission: str                      # "run_{key}_job"
    scope_fields: tuple[ScopeField, ...] = ()
    config_schema: type[pydantic.BaseModel] | None = None
    variant_key: str | None = None                # "task" for post-processing

    @classmethod
    def variants(cls) -> list[JobTypeVariant]: ...
    @classmethod
    def validate_params(cls, params: dict, project: Project) -> dict: ...
```

`MLJob.config_schema = PipelineRequestConfigParameters` (needs #1272's typed version, or a small
lift of it), `PostProcessingJob.variants()` reads `POSTPROCESSING_TASKS`, and the endpoint in §3.1 is
a serialization of these class attributes. Note `VALID_JOB_TYPES` itself does not change, so no
state-only migration is triggered — adding attributes to existing classes is not a `choices` change
(CLAUDE.md's rule applies to adding or renaming a type).

### 3.6 Per-job pipeline config

Extend the merge to three levels, keeping it in one place:

```python
Pipeline.get_config(project_id=None, overrides: dict | None = None)
# Pipeline.default_config  <  ProjectPipelineConfig.config  <  Job.params["config"]
```

and pass `job.params.get("config")` at the two call sites (`ami/jobs/models.py:574`,
`ami/ml/models/pipeline.py:316`) so the sync and async/NATS paths cannot diverge. #1279 ("propagate
pipeline config through NATS pull-mode tasks") is the adjacent work; this design assumes the merged
config is what reaches both dispatch modes.

The panel renders `PipelineRequestConfigParameters`' schema, prefilled from `config_defaults` (the
resolved project-level values), and **submits only the fields the operator actually changed**, so a
later change to the project default still applies to everything untouched. Because the schema is
`extra = "allow"` (measured, §2 item 4), the panel also offers an "Advanced" key/value editor for
service-specific keys the schema does not declare — which is how `request_*` parameters and
per-service options stay possible without a schema change.

### 3.7 Frontend shape

New files, following `ui/AGENTS.md` (kebab-case, `Server<Entity>` types, one hook per endpoint):

- `src/data-services/models/job-type.ts` — `ServerJobType`, `ServerJobTypeVariant`, `ServerConfigSchema`.
- `src/data-services/hooks/jobs/useJobTypes.ts` — `GET /jobs/types/`, cached per project.
- `src/components/form/schema-form/` — `schema-form.tsx` (walks the normalized schema),
  `schema-field.tsx` (one property → one control), `widgets.ts` (`ami_widget` → component map),
  `to-form-values.ts` / `to-api-values.ts`. Built on the existing `FormController` / `FormField` /
  `InputContent` primitives and `nova-ui-kit`, not a new form library (no JSON-Schema form dependency
  is in `ui/package.json` today, and `@rjsf/*` would not match the design system).
- `job-details-form.tsx` becomes: job type → variant → scope → config, with the config section
  collapsed under "Advanced" when every field has a default. `useCreateJob` stops hand-mapping five
  names and posts the assembled payload.

**One convention exception to agree on:** field labels and help text come from the server schema, not
from `translate(STRING.*)`. The alternative — a `STRING` key per task field — puts the copy in a
different repo location from the validation it describes and guarantees drift for any task added
after the panel ships. Proposal: static chrome stays translated, schema-supplied copy is English-only
for now, and we revisit if a second locale lands. Flagging it because `ui/AGENTS.md` states the rule
absolutely.

### 3.8 Read-back and re-run

`params` becomes readable on the Job detail response, and the Job detail page renders the config that
was used (the read-only key/value rows it already renders for stage params are the right shape). That
makes "re-run with these settings" a matter of seeding the panel from an existing job — the single
most-requested thing after "run it at all", and nearly free once §3.5 exists.

---

## 4. Phasing

Each phase is a PR-sized deliverable that leaves main working.

| Phase | Deliverable | Notes |
|---|---|---|
| **0** | Move each task's field comments into `Field(title=..., description=...)`; add `gt`/`lt` where a `@validator` encodes a bound that JSON Schema can express | No behaviour change; makes every later phase's output legible. Keep the root validators — they stay the authority |
| **1** | `JobType` descriptor attributes + `GET /jobs/types/` + `run_post_processing_job` granted to `MLDataManager`/`ProjectManager` | Backend only; admin actions untouched. Permission matrix test per the API checklist |
| **2** | Writable, schema-validated `params` on create; shared pydantic→DRF error mapper lifted from `actions.py` | The API can now create a class-masking job. Verify admin and API produce identical `params` |
| **3** | `SchemaForm` + new Create Job panel, post-processing first | ML keeps its current scope fields; gains the config section |
| **4** | Per-job pipeline config merge (§3.6) + read-back + re-run | Touches both dispatch paths — needs the async chaos runbook (`docs/claude/debugging/chaos-scenarios.md`) |
| **5** | Migrate capture-set sampling to the same mechanism | Retires the hardcoded kwargs union and the bug class behind #1369 |

Phases 1–2 unblock #1272 and #1361 from writing another Django form: both can ship their task with an
annotated schema and no form file at all.

---

## 5. Risks

1. **Pydantic v1 lock.** `django-pydantic-field==0.3.10` holds us on v1. The normalizer (§3.3) plus
   `x-ami-schema-version` is the hedge: a v2 migration changes the producer, not the client contract.
2. **Cross-field rules are server-only.** `_exactly_one_scope` and friends cannot be expressed in the
   schema, so the panel will show some errors only after submit. Mitigation: the panel owns scope
   selection (§3.4), so the common cross-field rule is structurally satisfied before submit.
3. **Copy quality.** Schema `description` text becomes user-facing UI copy. The existing help text in
   the admin forms is good and should be moved, not re-written from scratch — it is the best
   documentation these tasks have.
4. **Permission widening.** Granting `run_post_processing_job` to `MLDataManager` moves class masking
   from superuser-only to project-role. That is the point, but it is a real change in blast radius:
   masking rewrites classifications (it demotes the original and writes a new terminal one). Worth an
   explicit decision, and possibly a separate role than the one that can run ML jobs.
5. **Unbounded option lists.** Every `ami_entity` picker must hit a list endpoint that is filtered
   and paginated by project. The comment in `class_masking_form.py` about a DISTINCT timing out is
   the warning to heed.
6. **Two existing create paths must not break.** `new-job-dialog.tsx` and
   `session-details/process/process-now.tsx` both call `useCreateJob`; keeping `job_type_key`
   defaulted for one release covers them.

## 6. Open questions

1. **Does the panel offer `data_storage_sync` / `populate_captures_collection` / `regroup_events`?**
   They already have per-page entry points. Listing them in one place is discoverable but duplicates
   those flows.
2. **Does an ML job get a task-style variant?** A "pipeline" is effectively the ML job's variant, and
   modelling it that way would unify the panel's shape — but pipelines are database rows with
   per-project configs, not registry entries, so the analogy is imperfect.
3. **Exports.** `DataExportJob` takes its format and filters from the `DataExport` row, not
   `Job.params`. Folding `ExportRegistry` in as variants would make the panel complete; leaving it
   out keeps this design smaller. Recommend leaving it out of phases 1–4.
4. **Multi-scope runs.** The admin action creates one Job per selected row. The panel as designed
   creates one Job. Is bulk (e.g. "run tracking on these 12 sessions") in scope, or does that stay an
   admin capability?
5. **The i18n exception (§3.7)** needs a call from whoever owns the frontend conventions.

## 7. Worked example — class masking, end to end

Descriptor (abridged) from `GET /jobs/types/?project_id=18`:

```jsonc
{
  "key": "post_processing", "name": "Post processing",
  "permission": "run_post_processing_job", "allowed": true, "variant_key": "task",
  "variants": [{
    "key": "class_masking", "name": "Class masking",
    "scope": [{"field": "source_image_collection_id", "widget": "capture_set",
               "required": true, "label": "Capture set"}],
    "config_schema": {
      "type": "object", "additionalProperties": false,
      "x-ami-schema-version": 1,
      "properties": {
        "taxa_list_id": {"type": "integer", "title": "Taxa list to keep",
                         "description": "Classes whose taxon is not in this list are masked out…",
                         "ami_widget": "entity", "ami_entity": "taxa_lists"},
        "algorithm_id": {"type": "integer", "title": "Source classifier",
                         "description": "The classification algorithm whose terminal predictions are re-scored.",
                         "ami_widget": "entity", "ami_entity": "algorithms",
                         "ami_entity_filters": {"task_type": "classification"}},
        "reweight": {"type": "boolean", "default": true, "title": "Reweight scores",
                     "description": "Renormalise the kept classes to sum to 1…"}
      },
      "required": ["taxa_list_id", "algorithm_id"]
    }
  }]
}
```

The panel renders: a capture-set picker (scope), two entity pickers, one checkbox — no frontend code
naming class masking anywhere. On submit:

```jsonc
POST /api/v2/jobs/?start_now
{
  "name": "Class masking on Panama 2024",
  "project_id": 18,
  "job_type_key": "post_processing",
  "source_image_collection_id": 142,
  "params": {"task": "class_masking",
             "config": {"taxa_list_id": 7, "algorithm_id": 31, "reweight": true}}
}
```

The serializer copies `source_image_collection_id` into `params["config"]` (§3.4), validates against
`ClassMaskingConfig`, and `PostProcessingJob.run` consumes it exactly as the admin-created job does
today — `params.get("task")`, `params.get("config")`, `task_cls(job=job, **config)`.


