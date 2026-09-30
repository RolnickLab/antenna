# Jobs panel: how a job type appears in the Create Job dialog

The Create Job dialog is generated from `GET /api/v2/jobs/types/?project_id=N`. A job type or
post-processing task shows up there, with a working form, once it declares the attributes below.
No frontend change is needed. Design history: branch `feat/jobs-panel-design`,
`docs/claude/planning/2026-09-18-jobs-panel-schema-driven-design.md`. PR #1447.

## Where things live

| What | File |
|---|---|
| `ScopeField`, schema normalizer, docstring → description | `ami/jobs/descriptors.py` |
| `JobType` attributes, `validate_params`, project-scope id checks | `ami/jobs/models.py` (`class JobType`, `PostProcessingJob`, `check_entities_in_project`) |
| Response builder `describe_job_types`; `params` validation on create | `ami/jobs/serializers.py` (`JobSerializer.validate`) |
| The gated `types` action | `ami/jobs/views.py` (`JobViewSet.types`) |
| Member allowlist and staff-only settings | `ami/ml/post_processing/registry.py` (`MEMBER_POST_PROCESSING_TASKS`, `staff_only_config_fields`) |
| Tests (permission matrix, query count, params validation) | `ami/jobs/tests/test_job_types.py` |

## Making a job type creatable

On the `JobType` subclass:

- **Docstring**: its first paragraph is the help text under the job type select.
- `user_creatable = True`: without it the type is not listed and `POST /jobs/` refuses it.
- `scope_fields`: what the job runs on, as `ScopeField`s (`PIPELINE_SCOPE`, `CAPTURE_SET_SCOPE`,
  `STATION_SCOPE`, or your own). `target="job"` means a top-level serializer field backed by a Job
  column. `target="config"` means the value goes inside `params["config"]`.
- `required_fields` / `required_params`: checked on create (same shape as #1407).
- `config_schema`: a pydantic (v1) model for `params["config"]`. It is rendered as a form and
  validated by `JobType.validate_params(project, user, params)`.
- `variant_key` + `variants()`: for types whose work is picked from a registry (post-processing).

## Making a post-processing task appear

Register it in `POSTPROCESSING_TASKS` and give the task class a docstring. Its `config_schema`
fields become the form:

```python
taxa_list_id: int = pydantic.Field(
    ..., title="Taxa list to keep", description="Classes outside this list are masked out.",
    ami_widget="entity", ami_entity="taxa/lists",
)
```

- `title` / `description` are the label and help text (English only, not translated).
- `ami_widget="entity"` + `ami_entity="<api route>"` (+ `ami_entity_filters`) renders a picker
  that pages that list endpoint. The same hint makes the server check that the id belongs to the
  job's project (`_entity_queryset` in `ami/jobs/models.py`). Add a route there if the entity is
  new; an unmapped entity is not project-checked.
- `gt` / `lt` / `ge` / `le` become the form's numeric bounds.
- `source_image_collection_id` and `event_ids` are treated as scope, not settings
  (`PostProcessingJob.SCOPE_CONFIG_FIELDS`). If a config has both, the dialog shows both and the
  task's own root validator enforces "exactly one". `occurrence_id` is hidden (admin-only path).
- Members can start a task only if it is in `MEMBER_POST_PROCESSING_TASKS`, and can change only
  the listed fields. Superusers can start any task and change any setting. Non-superusers do not
  receive the other fields in the schema.

## Gotchas

- `ObjectPermission.has_permission` returns True for every request, and a `detail=False` action
  never reaches the object check. `types` gates itself (authenticated project member or superuser).
- Pydantic is v1 here (`Model.schema()`, `__fields__[...].field_info`). The normalizer is the one
  place that shapes schemas; `x-ami-schema-version` marks its output.
- `params` is fixed after creation: `JobSerializer.validate` drops it on update.
- `assertNumQueries` for `types` counts the request's savepoint pair (6 total).
