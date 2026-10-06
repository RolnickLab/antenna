# Jobs panel: how a job type appears in the Create Job dialog

The Create Job dialog is generated from `GET /api/v2/jobs/types/?project_id=N`. A job type or
post-processing task shows up there, with a working form, once it declares the attributes below.
No frontend change is needed. Design history: branch `feat/jobs-panel-design`,
`docs/claude/planning/2026-09-18-jobs-panel-schema-driven-design.md`. PR #1447.

## The contract in one paragraph

Each job type has one pydantic model describing everything a new job of that type takes
(`JobType.config_schema`; post-processing has one per task). `GET /jobs/types/` serves each model's
JSON Schema unchanged, wrapped in `JobTypeDescription` (`ami/jobs/schemas.py`), plus the picker
headings in use (`groups`, `JobGroup` order). The dialog shows one grouped picker: a type without
variants is one entry, a type with variants (post-processing) contributes one entry per variant. The dialog renders
the schema as its form and posts `{"name", "delay", "project_id", "job_type_key", "params": {"config":
{...}}}` (plus `"task"` for post-processing). `JobSerializer.validate` hands `params` to
`JobType.validate_params`, which parses it with the model and checks every id against the project;
config fields named in `JOB_COLUMNS` (`pipeline_id`, `source_image_collection_id`, ...) are also set on
the Job's columns so the jobs list can filter on them.

## Where things live

| What | File |
|---|---|
| Per-type input models (`MLJobConfig`, ...) and the response models | `ami/jobs/schemas.py` |
| `JobType.describe`, `validate_params`, `column_ids`, `describe_job_types`, project-scope id checks | `ami/jobs/models.py` |
| `params` validation on create | `ami/jobs/serializers.py` (`JobSerializer.validate`) |
| The gated `types` action | `ami/jobs/views.py` (`JobViewSet.types`) |
| Per-task feature flags | `ami/main/models.py` (`ProjectFeatureFlags`), `BasePostProcessingTask.feature_flag` |
| `run_post_processing_job` for ML data managers | `ami/users/roles.py`, `ami/main/migrations/0096_grant_run_post_processing_to_ml_data_manager.py` |
| Form mapping and payload | `ui/src/components/form/schema-form/` (`schema-to-fields.ts`, `build-job-payload.ts`) |

## Making a job type creatable

On the `JobType` subclass: `user_creatable = True`, a `label` and `description` (in `gettext_lazy`),
a `group` (`JobGroup`, the picker heading), and a `config_schema` model in `ami/jobs/schemas.py`.
`label` is what users see in the picker, the jobs list and job details ("Process captures"); `name`
stays the fixed internal name used in logs and stage names. Required inputs are pydantic-required fields; Job
columns are fields named as in `JOB_COLUMNS`.

## Making a post-processing task appear

Register it in `POSTPROCESSING_TASKS`, give it `feature_flag` (a `ProjectFeatureFlags` field you
add, default off), a `label`, a `group` and a `description`. Never rename a task's `name`: it is the
lookup key for the task's Algorithm row (`BasePostProcessingTask.__init__`), so a rename starts a new
algorithm. The jobs list names a post-processing job by its task's `label` (`PostProcessingJob.label_for`). When a project turns the flag on, ML data managers and
project managers can run the task with any settings; while it is off the task is hidden, refused on
create through the API, and its jobs cannot be re-run except by a superuser. The Django admin action
still lets superusers start it, so staff can try a method on a project before turning it on.

The served schema is `config_schema.schema()` unchanged; the same rules apply to the per-type models
in `ami/jobs/schemas.py`. Write it for the form:

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
change it. It is returned on the job detail response, not the list. Ids that are also Job columns
(pipeline, capture set, station, capture) are stored in both places.

## Gotchas

- `ObjectPermission.has_permission` returns True for every request, and a `detail=False` action
  never reaches the object check. `types` gates itself (authenticated project member or superuser).
- Pydantic is v1 here (`Model.schema()`). A move to v2 changes the served shape (`$defs`, `anyOf` for optionals); update the frontend mapping with it.
- `assertNumQueries` for `types` counts the request's savepoint pair (6 total).
