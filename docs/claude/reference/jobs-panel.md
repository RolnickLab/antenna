# Jobs panel: how a job type appears in the Create Job dialog

The Create Job dialog is generated from `GET /api/v2/jobs/types/?project_id=N`. A job type or
post-processing task shows up there, with a working form, once it declares the attributes below.
No frontend change is needed. Design history: branch `feat/jobs-panel-design`,
`docs/claude/planning/2026-09-18-jobs-panel-schema-driven-design.md`. PR #1447.

## Where things live

| What | File |
|---|---|
| `ScopeField` (Job columns), `describe()`, `entity_fields()` | `ami/jobs/descriptors.py` |
| `JobType` attributes, `validate_params`, project-scope id checks, flag check on re-run | `ami/jobs/models.py` (`JobType`, `PostProcessingJob.enabled_tasks`, `check_entities_in_project`, `Job.check_custom_permission`) |
| Response builder `describe_job_types`; `params` validation on create | `ami/jobs/serializers.py` (`JobSerializer.validate`) |
| The gated `types` action | `ami/jobs/views.py` (`JobViewSet.types`) |
| Per-task feature flags | `ami/main/models.py` (`ProjectFeatureFlags`), `BasePostProcessingTask.feature_flag` |
| `run_post_processing_job` for ML data managers | `ami/users/roles.py`, `ami/main/migrations/0096_grant_run_post_processing_to_ml_data_manager.py` |
| Tests | `ami/jobs/tests/test_job_types.py`, `ui/src/components/form/schema-form/tests/` |

## Making a job type creatable

On the `JobType` subclass:

- `description`: help text under the job type select. Wrap it in `gettext_lazy`; it falls back to
  the docstring's first paragraph.
- `user_creatable = True`: without it the type is not listed and `POST /jobs/` refuses it.
- `scope_fields`: the Job columns it runs on (`PIPELINE_SCOPE`, `CAPTURE_SET_SCOPE`,
  `STATION_SCOPE`), sent as top-level serializer fields.
- `required_fields` / `required_params`: checked on create (same shape as #1407).
- `config_schema`: a pydantic (v1) model for `params["config"]`, rendered as a form and validated
  by `JobType.validate_params(project, user, params)`.
- `variant_key` + `variants(project)`: for types whose work is picked from a registry.

## Making a post-processing task appear

Register it in `POSTPROCESSING_TASKS`, give it `feature_flag` (a `ProjectFeatureFlags` field you
add, default off) and a `description`. When a project turns the flag on, ML data managers and
project managers can run the task with any settings; while it is off the task is hidden, refused on
create, and its jobs cannot be re-run except by a superuser.

The served schema is `config_schema.schema()` unchanged. Write it for the form:

```python
source_image_collection_id: int | None = pydantic.Field(
    None, title=_("Capture set"), ami_widget="entity", ami_entity="captures/collections",
)
occurrence_id: int | None = pydantic.Field(None, ami_widget="hidden", ami_entity="occurrences")
cost_threshold: float = pydantic.Field(0.2, title=_("Cost threshold"), description=_("..."), ge=0)
appearance_weight: float = pydantic.Field(1.0, title=_("Appearance weight"), ami_advanced=True)
```

- Give every visible field a `title` (pydantic's own is title-cased from the name) and a
  `description`, both in `gettext_lazy`: they are served in the request's language.
- `ami_widget="entity"` + `ami_entity="<api route>"` (+ `ami_entity_filters`) renders a picker,
  and the server checks the id belongs to the job's project (`_entity_queryset`; add the route
  there for a new entity, or it is not checked). Check the target viewset can filter by every
  `ami_entity_filters` key; DRF ignores unknown filters silently.
- `ami_widget="hidden"` keeps a field out of the form; `ami_advanced=True` puts it under the
  collapsed "More settings".
- Use `typing.Literal` for choices, not an `Enum` class (which becomes a `$ref`).
- Cross-field rules (such as "exactly one of capture set or sessions") stay in the model's
  validators; their errors show in the dialog's general error block.

## Where the settings are stored

`Job.params`, validated and filled with every default on create, then fixed: an update cannot
change it. It is returned on the job detail response, not the list. Job types without a settings
model store nothing there; their choices are Job columns (pipeline, capture set, station).

## Gotchas

- `ObjectPermission.has_permission` returns True for every request, and a `detail=False` action
  never reaches the object check. `types` gates itself (authenticated project member or superuser).
- Pydantic is v1 here (`Model.schema()`). A move to v2 changes the served shape (`$defs`, `anyOf` for optionals); update the frontend mapping with it.
- `assertNumQueries` for `types` counts the request's savepoint pair (6 total).
