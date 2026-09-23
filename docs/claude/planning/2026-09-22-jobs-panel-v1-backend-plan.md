# Jobs panel v1 backend — implementation plan and its open blockers

**Status:** planned and reviewed, not started. Decisions recorded 2026-09-23 (see below). No implementation code written.  
**Date:** 2026-09-22  
**Plans:** phases 1&ndash;3 of `2026-09-18-jobs-panel-schema-driven-design.md` §4 (the backend contract). Phase 4, the `SchemaForm` UI, is not planned here.

## Summary

The v1 backend slice makes the jobs API describe itself and accept per-job configuration, so that a later UI can render a Create Job form for any job type without hardcoding its knobs. Phase 1 moves every post-processing task's documentation out of Python comments and Django form files and onto the pydantic config fields themselves, so the generated JSON Schema carries real labels, help text and numeric bounds instead of "Source Image Collection Id". Phase 2 attaches a descriptor (description, permission, scope fields, config schema, variants) to each job type class and serves all of them from a new read endpoint, GET /api/v2/jobs/types/?project_id=N, with an `allowed` flag resolved for the requesting user; it also grants `run_post_processing_job` to the roles that can already run ML jobs, without which the feature stays superuser-only. Phase 3 makes `Job.params` writable on create and validates it against the resolved task's pydantic schema, so a bad config returns 400 with per-field errors instead of failing inside a Celery worker after the job already shows as started. The serializer copies the scope ids from the Job's own columns into `params["config"]` server-side, so an API-created job and an admin-created job produce byte-identical params and `PostProcessingJob.run` is untouched. Only two post-processing tasks exist in this worktree (class masking and small size filter), not the four the design doc's phasing table assumes. No schema migration is needed anywhere in phases 1-3: `VALID_JOB_TYPES` is not changed, so `job_type_key.choices` is unchanged, and `Job.params` already exists as a JSONField. The one optional migration is a belt-and-suspenders data migration for the role grant, following the precedent at ami/main/migrations/0095.

The plan below was produced from a reading of the post-processing framework, the jobs model and API, the permission roles and the frontend create-job form, then reviewed by three independent critics: one checking that every file, class and line it cites actually exists, one checking it against the approved design, and one hunting the bug classes that do not show up in a diff. All three returned `needs-changes`. **Ten blockers are unresolved, so the step list below is not yet safe to implement as written.**

## Decisions and corrections, 2026-09-23

**The premise about task count is out of date.** This plan was written against a worktree without the tracking work. The tracking pull request (#1272) adds a third post-processing task, `tracking`, and has already built a tracking-only version of much of phases 2 and 3:

- `params` is writable on create and validated by `validate_post_processing_params` in `ami/jobs/serializers.py`: a task allowlist (`MEMBER_POST_PROCESSING_TASKS`), the task's pydantic schema, staff-only settings, and event and capture-set ids checked against the job's project.
- A PATCH without `job_type_key` drops `params`; with it, the same validation runs (B9, mostly closed for tracking).
- `Job._members_may_run_post_processing` re-checks the task, the staff-only settings and the project's tracking flag whenever someone other than a superuser runs or retries a post-processing job.
- `run_post_processing_job` is granted to `MLDataManager` (and so `ProjectManager`) in `ami/users/roles.py`, with data migration 0101.
- The interface pull request (#1432) has a hand-built "Run tracking" dialog. It is what this panel replaces.

**Decisions:**

1. **Role:** `MLDataManager`, as recommended. Already applied in #1272, so step 8 here becomes "nothing to do" once #1272 merges.
2. **Tracking is the panel's first user.** Annotate `TrackingConfig` in phase 1 alongside the other two tasks. Phase 3's `JobType.validate_params` should absorb `validate_post_processing_params` from #1272 rather than write a parallel version. After that, every registered post-processing task appears in the panel, as it does in the Django admin. Widening beyond tracking still needs B7's project scoping of every id inside each task's config.
3. **Task count:** three once #1272 merges (class masking, small size filter, tracking). Rank rollup (#1361) joins when it lands.
4. **Sequencing:** build this plan's backend steps after #1272 merges, so the jobs serializer and its validation contract change in one place, once.

## Two findings that change the shape of the work

1. **Only two post-processing tasks exist.** The design doc's phasing table names four (class masking, small size filter, rank rollup, tracking), but `ami/ml/post_processing/` contains only `class_masking` and `small_size_filter`. Rank rollup and tracking have no code to annotate. Nothing in phases 1&ndash;3 depends on the count &mdash; a new task joins by editing `POSTPROCESSING_TASKS` and annotating its schema &mdash; but v1 promises less than the doc's wording implies.

2. **No schema migration is needed anywhere in phases 1&ndash;3.** `VALID_JOB_TYPES` is not changed, so `Job.job_type_key`'s `choices` is unchanged, and `Job.params` already exists as a `JSONField`. The only migration is an optional data migration for the role grant, following the precedent at `ami/main/migrations/0095`.

## Decisions that need a human

### 1. Which roles get `run_post_processing_job`? The permission is declared and migrated but granted to no role, so post-processing is superuser-only today.

**Recommendation:** Grant it to `MLDataManager` (and therefore `ProjectManager`, which unions MLDataManager's set) — the same roles that can already run ML jobs. Ship the role-class edit plus an explicit data migration in the style of ami/main/migrations/0095_grant_sync_deployment_to_mldatamanager.py.

The design doc says explicitly this must be decided by a human before phase 2 ships. Class masking rewrites classifications (originals demoted, not deleted), which is arguably a wider blast radius than ML reprocessing; if that judgement goes the other way the alternative is a new role, and that changes step 8 and the `allowed` flag in step 7. Note the mechanical trap: a data migration that grants a permission absent from the role class is wiped on the next `migrate`, because `create_roles_for_project` (ami/users/roles.py:224-230) clears and rebuilds every group's grants from the role class on every `post_migrate`. The role-class edit is the load-bearing change; the migration is only explicitness.

### 2. Should creating a post-processing Job require `run_post_processing_job`, or only running it?

**Recommendation:** Require the job type's run permission at create time as well, enforced in `perform_create` before `serializer.save()`.

Today `BaseModel.check_permission` maps the create action to `create_job` and never consults `job_type_key` (ami/base/models.py:196-206), so a BasicMember can POST a post-processing job today; with `?start_now` it gets a PermissionDenied only after the row is committed (ami/jobs/views.py:309-317), leaving an orphan job stuck in CREATED forever. Tightening create is the safer default but it is a real permission-policy change that could break an existing client, so it wants a human call rather than being slipped in.

### 3. Does v1 ship with two post-processing tasks, or wait for rank rollup and tracking?

**Recommendation:** Ship with the two that exist (`class_masking`, `small_size_filter`). Nothing in phases 1-3 assumes a task count, and a new task joins by editing `POSTPROCESSING_TASKS` plus annotating its schema — no endpoint, serializer or migration change.

The design doc's phasing table names four tasks ("class masking, small size filter, rank rollup or tracking") but `ami/ml/post_processing/` in this worktree contains no rank-rollup and no tracking module. Any plan that budgets four schema-annotation steps is planning work that has no code to attach to. This is a scope/expectation call about what "v1" promises, not a technical one.

### 4. Schema `title`/`description` become user-facing UI copy in English only, bypassing `translate(STRING.*)`, which ui/AGENTS.md states as an absolute rule.

**Recommendation:** Accept the exception: static chrome stays translated, schema-supplied copy is English-only, revisit if a second locale lands. Record the exception in ui/AGENTS.md when phase 4 lands rather than leaving it undocumented.

The alternative is a STRING key per task field, which puts the copy in a different repo from the validation it describes and guarantees drift for every task added after the panel ships. It is phase 4 work, but the decision constrains what phase 1 writes into the schemas, so it should be settled now. The frontend convention owner has to sign this off.

## The thirteen steps

Each step is independently commitable and names the test that pins it. Phase numbers refer to §4 of the design doc.

| # | Phase | What it does for the operator | Files | Migration |
|---|---|---|---|---|
| 1 | 1 | Let a task describe a config field's label, help text and picker in one place | `ami/ml/post_processing/fields.py`, `ami/ml/post_processing/tests/test_ami_field.py` | none |
| 2 | 1 | Show real labels and the allowed range on the small size filter's settings | `ami/ml/post_processing/small_size_filter.py`, `ami/ml/post_processing/tests/test_base_schema.py` | none |
| 3 | 1 | Show real labels and pickers on the class masking settings | `ami/ml/post_processing/class_masking.py`, `ami/ml/post_processing/tests/test_base_schema.py` | none |
| 4 | 1 | Stop the admin's copy of each setting's label from drifting from the task's own | `ami/ml/post_processing/admin/small_size_filter_form.py`, `ami/ml/post_processing/admin/class_masking_form.py`, `ami/ml/post_processing/tests/test_admin_form.py` | none |
| 5 | 2 | Let each job type say what it needs before it can run | `ami/jobs/job_types.py`, `ami/jobs/models.py`, `ami/jobs/tests/test_job_types.py` | none |
| 6 | 2 | Turn a task's settings schema into something a form can render directly | `ami/jobs/schema_normalizer.py`, `ami/jobs/tests/test_schema_normalizer.py` | none |
| 7 | 2 | Let the app ask which kinds of job it can run on a project, and what each one needs | `ami/jobs/serializers.py`, `ami/jobs/views.py`, `ami/jobs/tests/test_job_types_endpoint.py` | none |
| 8 | 2 | Let project managers and ML data managers run post-processing, not only superusers | `ami/users/roles.py`, `ami/main/migrations/00NN_grant_run_post_processing_to_mldatamanager.py`, `ami/users/tests/test_roles.py` | data migration (optional) |
| 9 | 3 | Report a bad setting against the field it belongs to, wherever the job was started from | `ami/base/pydantic_errors.py`, `ami/ml/post_processing/admin/actions.py`, `ami/base/tests/test_pydantic_errors.py` | none |
| 10 | 3 | Reject an unrecognised job type instead of silently creating an ML job | `ami/jobs/serializers.py`, `ami/jobs/tests/test_jobs.py` | none |
| 11 | 3 | Let a job carry its own settings, checked before the job is created | `ami/jobs/serializers.py`, `ami/jobs/tests/test_job_params.py` | none |
| 12 | 3 | Refuse a job the user is not allowed to run, before it is saved | `ami/jobs/views.py`, `ami/jobs/tests/test_job_params.py` | none |
| 13 | 3 | Stop a post-processing job being created in a state where nobody can run it | `ami/jobs/serializers.py`, `ami/jobs/models.py`, `ami/jobs/tests/test_job_params.py` | none |

## Blockers — resolve before writing code

These came from the adversarial review. Each is a concrete defect in the plan, with the evidence that proves it.

**B1. (step 7)** The new GET /jobs/types/ action has no authentication or permission gate, so it is world-readable. JobViewSet sets permission_classes = [ObjectPermission], and ObjectPermission.has_permission returns True unconditionally — only has_object_permission does any checking, and a detail=False action never triggers it. The plan's own test ("anonymous gets 401/403") therefore cannot pass, and the endpoint would return a per-project job-type/permission catalog for any project_id including draft projects.

- *Evidence:* ami/base/permissions.py:163-172 (`def has_permission(self, request, view): return True  # Always allow — object-level handles actual checks`); ami/jobs/views.py:231 (`permission_classes = [ObjectPermission]`)
- *Fix:* Add an explicit gate for the action: either a dedicated permission class following the UserMembershipPermission / ProjectPipelineConfigPermission pattern (ami/base/permissions.py:175-227, both of which override has_permission for object-less actions), or an in-action check that the request user is authenticated and can retrieve the resolved project (`Job(project=project).check_permission(request.user, "retrieve")`).

**B2. (step 7)** The stated resolution mechanism cannot produce the two error codes the step's tests require. JobViewSet sets neither require_project nor require_project_for_list, so `self.get_active_project()` calls the standalone helper with required=False. In that mode a missing project_id returns None (no 400) and a valid-but-nonexistent id also returns None (no 404) — the Http404 branch is gated on `required`. The plan explicitly forbids flipping the viewset-wide flag and forbids re-parsing the param by hand, leaving no path to the specified 404.

- *Evidence:* ami/base/views.py:53-59 (`if not project_id: return None` … `except Project.DoesNotExist: return None`) and ami/base/views.py:82-94 (`required = self.require_project or (...)` … `if not project and required: raise Http404`); ProjectMixin defaults at ami/base/views.py:67-68; JobViewSet class body ami/jobs/views.py:189-231 sets neither flag.
- *Fix:* Set the flag per-request inside the action before resolving, e.g. `self.require_project = True` then `project = self.get_active_project()` — this keeps the SingleParamSerializer 400 for `?project_id=abc`, gives the 400 for a missing param, and gives the 404 for a nonexistent id, without changing the class attribute that get_queryset also reads on the list action.

**B3. (step 7)** The `exclude` argument the step passes to the normalizer has no defined source for post-processing variants. Step 5 populates `scope_fields` only on MLJob, SourceImageCollectionPopulateJob, DataStorageSyncJob and RegroupEventsJob — PostProcessingJob is given `variant_key`/`variants()` instead, and JobTypeVariant is never given scope fields. Yet step 7's test asserts the class_masking variant's config_schema has "scope ids absent from properties".

- *Evidence:* Plan step 5 detail lists scope_fields targets and omits PostProcessingJob; the scope ids live on the pydantic configs, not on the job type — ami/ml/post_processing/class_masking.py:22-23 and ami/ml/post_processing/small_size_filter.py:15-16
- *Fix:* Give JobTypeVariant its own `scope_fields` (or an explicit `hidden_config_fields`) and populate it in PostProcessingJob.variants() from the task's known scope keys, then pass that as `exclude`. Otherwise the variant schema is emitted with `source_image_collection_id` and `occurrence_id` as bare integer properties.

**B4. (step 5)** Every job type except `unknown` is left user_creatable=True, so the descriptor endpoint advertises — and the step-10 ChoiceField accepts — four job types that are only ever created server-side with required FKs the API never sets. A `data_export` job created through the serializer has `data_export = None` and crashes in the worker; `data_storage_sync` needs a deployment; `regroup_events` and `populate_captures_collection` are built for the user elsewhere.

- *Evidence:* VALID_JOB_TYPES at ami/jobs/models.py:980-988 contains DataExportJob; DataExportJob.run dereferences `job.data_export.run_export()` (ami/jobs/models.py:878 region), and the only caller setting that OneToOne is ami/exports/views.py:80. Server-side creators: ami/main/api/views.py:431 and :1058, ami/main/admin.py:244. The existing serializer comment already records this ("datasync, etc. are created for the user", ami/jobs/serializers.py:55-56).
- *Fix:* Set `user_creatable = False` on DataExportJob, DataStorageSyncJob, RegroupEventsJob and SourceImageCollectionPopulateJob as well as UnknownJobType in step 5, and state that flipping one to True requires its scope fields to be creatable through the serializer. Add a test that the step-10 ChoiceField rejects `data_export`.

**B5. (step 12)** Step 12 enforces `job_type.required_permission()` (= `run_ml_job`) at create time, which would 403 every BasicMember's single-capture "Process now" job — the one ML create path the rest of the plan goes out of its way to protect. BasicMember holds `create_job` + `run_single_image_ml_job` but NOT `run_ml_job`, and `Job.check_custom_permission` rewrites the action to `run_single_image` whenever `source_image_single` is set. The plan's own step 13 relies on that rewrite existing, so the two steps contradict each other on the same codename.

- *Evidence:* ami/users/roles.py:94-101 (BasicMember.permissions = {…CREATE_JOB, RUN_SINGLE_IMAGE_JOB…}, no RUN_ML_JOB); ami/jobs/models.py:1389-1391 (`if self.source_image_single: action = "run_single_image"`); ui/src/pages/session-details/process/process-now.tsx:33-40 (posts sourceImage + startNow, no job_type_key)
- *Fix:* Do not build the codename from `required_permission()` in perform_create. Build the unsaved instance (as the existing code already does at ami/jobs/views.py:305) and call `obj.check_custom_permission(request.user, "run")`, which applies the single-image rewrite. Add a step-12 test that a BasicMember can still POST an ML job with `source_image_single_id` + `?start_now` and gets 201.

**B6. (step 5, 6, 7)** No step declares `scope` for post-processing variants, yet §3.1 and the §7 worked example both require it and step 6's normalizer `exclude` and step 7's test depend on it. Step 5 sets `scope_fields` only on MLJob, SourceImageCollectionPopulateJob, DataStorageSyncJob and RegroupEventsJob, and defines `PostProcessingJob.variants()` as reading "key, name, docstring and config_schema" — scope is never sourced. Step 7 then passes "the scope field names" to the normalizer as `exclude` with nothing to pass, and asserts "scope ids absent from properties". `JobTypeVariant`'s fields are never enumerated anywhere in the plan.

- *Evidence:* Design doc lines 519-521 (variant carries `"scope": [{"field": "source_image_collection_id", "widget": "capture_set", "required": true, "label": "Capture set"}]`) and §3.3 ("strips fields the panel supplies itself (the scope ids listed in `scope`)"); ami/ml/post_processing/class_masking.py:21-22 and small_size_filter.py:15-16 (both configs carry `source_image_collection_id` and `occurrence_id`)
- *Fix:* Give `JobTypeVariant` an explicit `scope_fields: tuple[ScopeField, ...]` and have `PostProcessingJob.variants()` populate it — either from a new `scope_fields` class attribute on `BasePostProcessingTask` subclasses, or from a `ScopeField` annotation on the config's scope fields. Also state what happens to `occurrence_id`, which has no Job FK column: either it is a declared scope entry the panel renders, or the plan must say it stays unreachable in v1.

**B7. (step 11)** Cross-tenant write. Step 11 opens `params.config` to any API caller, but every object id inside a post-processing config is resolved globally with no project filter. `ClassMaskingTask._scoped_classifications` does `Occurrence.objects.filter(pk=config.occurrence_id)` and `SourceImageCollection.objects.get(pk=config.source_image_collection_id)`; `ClassMaskingTask.run` does `Algorithm.objects.get(pk=config.algorithm_id)` and `TaxaList.objects.get(pk=config.taxa_list_id)`. `job.project` is never consulted by either task. The plan validates `config` only against the pydantic schema (types + the one-scope root validator), which checks nothing about ownership. Today this is unreachable because only staff hit it through the admin; phase 3 makes it a first-class API surface.

- *Evidence:* ami/ml/post_processing/class_masking.py:310, :318, :331, :335; ami/ml/post_processing/small_size_filter.py:48, :56; ami/jobs/models.py:906-916 (`config = params.get("config", {})` then `task_cls(job=job, **config)`)
- *Fix:* In `JobSerializer.validate()`, resolve every id-bearing config field against a project-scoped queryset (`SourceImageCollection.objects.filter(project=project)`, `Occurrence.objects.filter(project=project)`, `TaxaList` / `Algorithm` scoped the way `visible_for_user` does) and 400 on a miss, before instantiating the pydantic model. Add the defence-in-depth check inside the tasks too (`.filter(project=self.job.project)`), since the schema cannot express it. Add a test: member of project A posts a class-masking job with `project_id=A` and `params.config.occurrence_id` = an occurrence in project B → 400, and assert no Classification in B was modified.

**B8. (step 12)** The create-time permission check breaks the single-capture "Process now" button for every BasicMember. Step 12 checks `job_type.required_permission()`, defined in step 5 as `f"run_{cls.key}_job"` → `run_ml_job` for `MLJob`. `BasicMember.permissions` contains `CREATE_JOB` and `RUN_SINGLE_IMAGE_JOB` (`run_single_image_ml_job`) but **not** `RUN_ML_JOB`. `Job.check_custom_permission` handles this by rewriting the action to `run_single_image` when `source_image_single` is set; `required_permission()` has no such rewrite and cannot, because it is a classmethod with no instance. Failure scenario: a BasicMember clicks Process now on one capture → POST /jobs/?start_now with `source_image_single_id=N` and no `job_type_key` → today it creates and enqueues; after step 12 it returns 403. The same bug makes step 7's `allowed` flag report `false` for `ml` to a BasicMember who can in fact run single-capture jobs.

- *Evidence:* ami/users/roles.py:89-97 (BasicMember has CREATE_JOB + RUN_SINGLE_IMAGE_JOB, not RUN_ML_JOB); ami/main/models.py:448-449 (`RUN_ML_JOB = "run_ml_job"`, `RUN_SINGLE_IMAGE_JOB = "run_single_image_ml_job"`); ami/jobs/models.py:1388-1396; ui/src/pages/session-details/process/process-now.tsx:33
- *Fix:* Do not introduce a parallel `required_permission()` for the create check. Build the unsaved `obj` as `perform_create` already does and call `obj.check_custom_permission(self.request.user, "run")`, which already applies the single-image rewrite and the job-type-aware codename. If step 5 keeps `required_permission()` for the `types` endpoint, give it the `source_image_single` caveat in its docstring and compute step 7's `allowed` for `ml` as `run_ml_job OR run_single_image_ml_job`. Add the regression test: BasicMember POSTs an ML job with `source_image_single_id` and `?start_now` → 201 and enqueued.

**B9. (step 11)** `params` becomes writable on PATCH/PUT, and the validation step 11 describes cannot run there. `JobViewSet` is a full ModelViewSet and `get_serializer_class` returns `JobSerializer` for every non-list action, so adding `params` to `JobSerializer.Meta.fields` makes it writable on `update`/`partial_update` as well as `create`. On a partial update DRF does not apply field defaults, so `validated_data` has no `job_type_key`; step 11's "resolve the job type from the validated `job_type_key`" either raises `KeyError` (500) or silently skips validation and stores the blob. Failure scenario: an MLDataManager (has `update_job`) PATCHes an existing post-processing job with `{"params": {"task": "class_masking", "config": {"occurrence_id": <other project>, "taxa_list_id": 1, "algorithm_id": 1}}}`, then POSTs /jobs/{id}/retry/ — arbitrary unvalidated config reaches the worker.

- *Evidence:* ami/jobs/views.py:189 (`class JobViewSet(DefaultViewSet, ProjectMixin)`), :233-243 (`get_serializer_class` returns `JobSerializer` for everything but list); ami/jobs/serializers.py:180; ami/users/roles.py:140 (`UPDATE_JOB` on MLDataManager)
- *Fix:* Either add `params` to `read_only_fields` and accept it only through a create-specific serializer, or have `validate()` fall back to `self.instance.job_type_key` when `job_type_key` is absent and re-run the full variant + schema validation on every write. Add a test: PATCH `params` on an existing job with garbage config → 400 (or 405/ignored), and PATCH with a cross-project id → 400.

**B10. (step 7)** The new `GET /jobs/types/` endpoint has no permission gate at all. `JobViewSet` sets `permission_classes = [ObjectPermission]`, whose `has_permission` unconditionally returns `True` — object-level checks only fire via `get_object()`, which a `detail=False` action never calls. The plan adds no `get_permissions` override. Failure scenario: `curl -s 'https://…/api/v2/jobs/types/?project_id=17'` with no Authorization header returns 200 with the full catalog, including for a draft project that `check_permission("retrieve")` would otherwise hide — confirming the project exists and is named. The plan's own test ("anonymous gets 401/403") will fail against this code. It gets worse in phase 8, where `config_defaults` is described as project-resolved.

- *Evidence:* ami/base/permissions.py:168-172 (`def has_permission(self, request, view): return True`); ami/jobs/views.py:231 (`permission_classes = [ObjectPermission]`); ami/base/models.py:190-195 (draft-project gate lives in `check_permission("retrieve")`, never reached)
- *Fix:* Override `get_permissions` (or add a `has_permission` branch in the style of `ProjectPipelineConfigPermission`, ami/base/permissions.py:186-198) so the `types` action builds an unsaved `Job(project=project)` and calls `check_permission(request.user, "retrieve")`. Keep the anonymous/non-member assertions in the test, and add one for a draft project.

## Work the plan omits entirely

From the *CAN THIS PLAN ACTUALLY EXECUTE* review:

- No permission or authentication handling for the new detail=False /jobs/types/ action — ObjectPermission.has_permission is a no-op, so the plan needs a step that gates it
- No user_creatable=False decision for DataExportJob, DataStorageSyncJob, RegroupEventsJob or SourceImageCollectionPopulateJob, all of which require FKs the serializer never sets
- No source for the `exclude` field names the normalizer needs for post-processing variants (scope_fields is populated on every job type except the one that needs it)
- No `ami/base/tests/__init__.py` — the package the step-9 test file would live in does not exist
- No path for an occurrence-scoped post-processing job through the API; Job has no occurrence column and the scope fields are excluded from the emitted schema
- No descriptions on the two task classes (neither has a docstring), so variants() has nothing to read
- No step verifies that existing MLDataManager permission assertions in ami/main/tests.py are updated when the role set changes in step 8

From the *Does this match the approved design* review:

- Phase 4 entirely. The design doc defines the v1 slice as phases 1-4 — "a project member with the right role can run class masking … from the Jobs page" — and the plan stops at phase 3. Nothing in the plan is wrong for stopping there, but the backend slice alone does not make the doc's v1 sentence true; the plan should say what remains before the release it calls v1 is shippable.
- A `user_creatable = False` sweep over the job types the panel must not offer. Only `UnknownJobType` is handled; `DataExportJob` is not, and no step states the rule the doc gives ("Job types the UI must never offer … are omitted").
- The field list of `JobTypeVariant` and `ScopeField`. Step 5 names the two dataclasses and step 7 says the serializers emit "exactly the §3.1 shape", but no step enumerates `field`/`widget`/`entity`/`required`/`label` or the variant's own scope, which is what makes the §7 worked example reproducible.
- How the normalizer distinguishes an author-written title from pydantic's auto-generated one. Step 6 says it "replace[s] pydantic's auto-generated title-case" but pydantic v1 always emits a title, so a rule is needed (consult `model.__fields__[name].field_info.title is None` — the step's signature takes the model, so this is available, it is just unstated).

From the *WHAT BREAKS SILENTLY* review:

- Project-scoping of every object id inside `params.config`. The plan validates config shape but never ownership; `occurrence_id`, `taxa_list_id` and `algorithm_id` have no Job column and no queryset, and even the column-copied `source_image_collection_id` is unscoped (ami/jobs/serializers.py:284, `queryset=SourceImageCollection.objects.all()` with a standing @TODO). No step and no risk entry mentions this.
- A permission gate for the new `types` action. `ObjectPermission.has_permission` returns True unconditionally, so a `detail=False` action is ungated; the plan adds no `get_permissions` override and no draft-project handling.
- Making `params` safe on update. The plan reasons carefully about list vs detail exposure but never about PATCH/PUT, which the same `Meta.fields` change enables.
- Re-validation on `retry` and `run`. `POST /jobs/{id}/retry/` and `/run/` re-execute `PostProcessingJob.run` against whatever is in `Job.params` at that moment. Nothing re-checks the config against the schema or the project, so a job whose params were valid at create time (or were written by an older schema version) runs unchecked.
- A statement of what happens to jobs already in the database whose `params` were written by the admin. Step 11's byte-identical rule is asserted by one test but there is no audit of existing rows, and `x-ami-schema-version` is only added to the served schema, never stored alongside a job's params.
- Behaviour when `Job.params` is present but `job_type_key` resolves to `UnknownJobType`. Step 10 blocks the slug at the serializer, but rows already in the database with an unrecognised `job_type_key` still exist and `get_job_type_by_key` returns `None` (a sentinel, not a raise) at ami/jobs/models.py:991-993.
- An explicit note that `ami/base/models.py:213` uses a bare `assert self._meta.model_name is not None` in `check_custom_permission` — production code on the exact path steps 7 and 12 build on, stripped under `python -O`, which this repo's own CLAUDE.md forbids. Pre-existing, but the plan touches this call path and could fix it in step 12.

## Risks carried forward

- The role grant is the whole release. `run_post_processing_job` is granted to no role today, so if step 8's decision slips, phases 1-3 ship a jobs form that only superusers can use. The design doc says this decision must be made before phase 2 ships, not after.
- A data migration that grants a permission absent from the role class is silently wiped on the next `migrate`. `create_roles_for_project` calls `group.permissions.clear()` and `remove_perm` over every existing object permission before re-adding the role's current set, and it runs on every `migrate` via `post_migrate`. Step 8 must land the roles.py edit and the migration together, and verification must check `GroupObjectPermission` rows rather than assuming migrate fixed it — `create_roles` swallows per-project exceptions with a warning and continues, so a partial sync is silent.
- Pydantic is pinned `<2.0` by `django-pydantic-field==0.3.10`. Every schema surface written here is v1: `Model.schema()`, `__fields__[...].field_info`, `.dict()`, `@root_validator`. A v2 bump would change `definitions` to `$defs`, `Optional[int]` to an `anyOf` with null, and the numeric keyword shape from Draft-7 to Draft 2020-12. The `x-ami-schema-version: 1` marker from step 6 is the hedge, but only if the normalizer stays the single producer — any code path that emits a raw `.schema()` bypasses it.
- Cross-field rules cannot be expressed in JSON Schema, so the panel will surface `_exactly_one_scope` failures only after submit. Step 9's non-field bucket is the mitigation, and a form generator that renders per-field errors only will silently swallow the most common validation failure in these schemas.
- `extra = "forbid"` on both config schemas means the API cannot accept a superset payload. Any bookkeeping key a generated form posts back inside `config` — a scope discriminator, a stray `job_type` — returns 400 rather than being ignored. The scope-copy in step 11 must write exactly the field names the schema declares.
- Only two post-processing tasks exist in this worktree. The design doc's phasing table assumes four, and any estimate, test matrix or release note derived from it is wrong by half.
- `JobSerializer` subclasses `JobListSerializer`, so anything added to the list serializer's `fields` lands on every row of every jobs list. Step 11 deliberately adds `params` to the subclass only; a later refactor that collapses the two serializers would start echoing config on the list endpoint and change its payload size.
- Two frontend callers create jobs and neither sends `job_type_key`. `process-now.tsx` builds its payload by hand with no form and has no UI test coverage. Keeping the serializer default through step 10 is what protects it; making the field required is a separate, breaking change.
- Post-processing job scope ids are config fields, not job columns, and the admin injects them rather than the operator choosing them. Step 11's scope copy is what reconciles the two models, but nothing in the schema marks which fields a form must hide or lock — a generator that renders every property will render the scope ids as bare integer inputs. That marker is phase 4 work and is not designed yet.
- `BasePostProcessingTask.__init__` does a `get_or_create` for an `Algorithm` row at task construction time, inside the worker rather than at job creation. A job created through the API therefore has no algorithm linkage to show in a form preview or a read-back view, which phase 5 will need to account for.

## Where this was produced

A workflow of eight agents: four parallel subsystem readers, one plan synthesiser, three adversarial critics. The full structured output, including every non-blocking finding and the readers' raw fact lists with file:line references, is not committed &mdash; regenerate it or ask the session that ran it.
