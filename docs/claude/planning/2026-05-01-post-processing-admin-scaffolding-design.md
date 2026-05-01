# Post-Processing Admin Scaffolding — Design

**Status:** Draft (awaiting user review)
**Date:** 2026-05-01
**Branch:** `feat/post-processing-admin-scaffolding`
**Author:** Michael Bunsen (with Claude Opus 4.7)

## Context

`ami/ml/post_processing/` currently ships one task on main: `SmallSizeFilterTask` (PR #954, merged). Two open PRs add more post-processing tasks and each independently grew its own admin-trigger plumbing:

- **PR #999** (`feat/postprocessing-class-masking`, mohamedelabbas1996, open since 2025-10-14) adds `class_masking` and `rank_rollup` tasks. Admin trigger uses hand-rolled HTML in the action method; no `forms.Form` class.
- **PR #1272** (`claude/revive-tracking-feature-OyMO3`, current author, open) adds `tracking` task. Admin trigger uses a `forms.Form` subclass in `ami/ml/post_processing/admin_forms.py` with scope-aware dropdown init and per-project Job partitioning.

Both PRs touch `ami/main/admin.py`, `ami/ml/post_processing/registry.py`, and add a near-identical `*_confirmation.html` template. Three independent ad-hoc patterns are emerging where one shared one would do.

The existing `SmallSizeFilterTask` already reads `size_threshold` from `Job.params['config']` (default `0.0008`) — but the admin trigger hardcodes empty config, so the knob is unreachable. There's even a TODO comment in `small_size_filter.py:14` asking *"Could we use a pydantic model for config validation if it's just for this task?"*. This precursor PR answers that question and lands the answer as the shared pattern.

## Goal

Land a small precursor PR that establishes the shared admin-trigger pattern for post-processing tasks, using `SmallSizeFilterTask` as the migration consumer. Both #999 and #1272 rebase onto it and adopt the pattern. No new domain logic, no PR coordination drama, no carving up another contributor's work.

Admin is **not** the long-term primary trigger surface for post-processing — REST API + UI will eventually drive this. The scaffolding here optimises for current-state needs (admin-only) without painting future API integration into a corner.

## Scope

### In

1. **Pydantic config schema contract** on `BasePostProcessingTask`
2. **`BasePostProcessingActionForm`** — django form base class, `cleaned_data → config` contract
3. **Parameterized confirmation template** + form-fieldset partial
4. **Migrate `SmallSizeFilterTask`** to new pattern:
   - Add `SmallSizeFilterConfig(size_threshold: float = 0.0008, source_image_collection_id: int)` pydantic model
   - Add `SmallSizeFilterActionForm` with one field: `size_threshold` (`FloatField`, validation: `0 < x < 1`)
   - Rewrite `SourceImageCollectionAdmin.run_small_size_filter` to render intermediate confirmation page using new template + form
5. **Tests** for scaffolding + migrated task

### Out

- Project-partitioning helper (defer to whichever multi-scope adopter lands first — #999 or #1272)
- REST API endpoints for triggering post-processing
- Management commands
- pgvector migrations (#1272 territory)
- Rank rollup (stays in #999 — PR coordination unnecessary now)
- Class masking (stays in #999)
- Tracking (stays in #1272)

## Module Layout

```
ami/ml/post_processing/
├── base.py                           # MODIFIED — +config_schema contract
├── registry.py                       # unchanged
├── small_size_filter.py              # MODIFIED — schema-validated config, .config now BaseModel
├── admin/                            # NEW
│   ├── __init__.py
│   ├── forms.py                      # BasePostProcessingActionForm
│   └── small_size_filter_form.py     # SmallSizeFilterActionForm
└── tests/                            # NEW directory (existing tests in ami/ml/tests.py)
    ├── __init__.py
    ├── test_base_schema.py
    ├── test_admin_form.py
    └── test_small_size_filter_admin.py

ami/templates/admin/post_processing/  # NEW
├── confirmation.html                 # parameterized shell
└── _form_fieldset.html               # partial — renders form fields uniformly

ami/main/admin.py                     # MODIFIED — run_small_size_filter rewrites onto new pattern
```

Path note: spec uses `ami/ml/post_processing/admin/` as user requested. Tracking PR's `admin_forms.py` (top-level module) becomes `admin/tracking_form.py` on its rebase.

## Pydantic Schema Contract

`BasePostProcessingTask` gains a required class attribute `config_schema: type[BaseModel]` and validates config at construction.

```python
# ami/ml/post_processing/base.py (sketch)
import pydantic

class BasePostProcessingTask(abc.ABC):
    key: str
    name: str
    config_schema: type[pydantic.BaseModel]   # NEW

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for attr in ("key", "name", "config_schema"):
            if not hasattr(cls, attr) or getattr(cls, attr) is None:
                raise TypeError(f"{cls.__name__} must define '{attr}' class attribute")

    def __init__(self, job=None, logger=None, **config):
        self.job = job
        # Validate config against schema. Raises pydantic.ValidationError on bad input.
        self.config: pydantic.BaseModel = self.config_schema(**config)
        # ... existing logger + algorithm setup unchanged ...
```

**Pydantic version:** repo uses Pydantic v1 (per `requirements/base.txt` + container-side memory). Use v1 syntax: `BaseModel`, `Field`, `validator`, `.dict()`. No `model_dump`/`model_validate`.

**Validation timing:**

- **Worker side (always):** `BasePostProcessingTask.__init__` validates. Bad config in a Job's params → task crashes with clear pydantic error in job logs.
- **Admin side (added in this PR):** the rewritten `run_small_size_filter` calls `SmallSizeFilterConfig(**form.to_config(), source_image_collection_id=collection.pk)` *before* `Job.objects.create`. Validation error → form re-renders with error, no Job created.

**Per-task schema example:**

```python
# ami/ml/post_processing/small_size_filter.py
class SmallSizeFilterConfig(pydantic.BaseModel):
    source_image_collection_id: int
    size_threshold: float = 0.0008

    @pydantic.validator("size_threshold")
    def _threshold_in_unit_interval(cls, v):
        if not (0.0 < v < 1.0):
            raise ValueError("size_threshold must be in (0, 1) exclusive")
        return v

    class Config:
        extra = "forbid"   # unknown keys rejected — catches typos
```

**Migration impact for existing in-flight Jobs:** none. `Job.params['config']` payloads already match the new schema (only `source_image_collection_id` is required; `size_threshold` defaults). Workers picking up old jobs after deploy will validate cleanly.

## Admin Form Base

```python
# ami/ml/post_processing/admin/forms.py
class BasePostProcessingActionForm(forms.Form):
    """Base for admin forms that build BasePostProcessingTask config dicts.

    Subclass adds knob fields. Override to_config() if mapping isn't 1:1
    (e.g. drop empty optional fields, derive computed values).
    """

    def to_config(self) -> dict:
        return dict(self.cleaned_data)
```

That's it. The form base is intentionally thin — it's a contract marker (so admin actions know which type of form to render) plus one helper. Scope-aware kwargs (`events=`, `collection=`) are subclass-specific and don't belong on the base.

## Confirmation Template

```html
{# ami/templates/admin/post_processing/confirmation.html #}
{% extends "admin/base_site.html" %}
{% load i18n admin_urls %}

{% block title %}{{ title }} | {{ site_title|default:_("Django site admin") }}{% endblock %}

{% block breadcrumbs %}
  <div class="breadcrumbs">
    <a href="{% url 'admin:index' %}">{% translate 'Home' %}</a>
    › <a href="{{ changelist_url }}">{{ model_meta.verbose_name_plural|capfirst }}</a>
    › {{ title }}
  </div>
{% endblock %}

{% block content %}
<form method="post">
  {% csrf_token %}

  {% block intro %}
    <p>You are about to run <strong>{{ task_label }}</strong> on
       <strong>{{ selected_count }}</strong> selected
       {{ model_meta.verbose_name }}{{ selected_count|pluralize }}.</p>
  {% endblock %}

  <fieldset>
    <legend>{% translate "Parameters" %}</legend>
    {% include "admin/post_processing/_form_fieldset.html" with form=form %}
  </fieldset>

  {% for pk in selected_pks %}
    <input type="hidden" name="_selected_action" value="{{ pk }}" />
  {% endfor %}
  <input type="hidden" name="action" value="{{ action_name }}" />
  <input type="hidden" name="confirm" value="1" />

  <div class="submit-row">
    <input type="submit" value="{{ submit_label|default:title }}" />
    <a href="{{ changelist_url }}">{% translate 'Cancel' %}</a>
  </div>
</form>
{% endblock %}
```

```html
{# ami/templates/admin/post_processing/_form_fieldset.html #}
{% for field in form %}
  <div class="form-row">
    {{ field.label_tag }}
    {{ field }}
    {% if field.help_text %}<p class="help">{{ field.help_text }}</p>{% endif %}
    {% for error in field.errors %}<p class="errornote">{{ error }}</p>{% endfor %}
  </div>
{% endfor %}
```

Per-task templates (e.g. tracking) extend the shell + override `{% block intro %}` for task-specific preamble. Small-size-filter uses bare shell.

## Admin Action Rewrite

```python
# ami/main/admin.py (sketch — only the changed action)
from ami.ml.post_processing.admin.small_size_filter_form import SmallSizeFilterActionForm
from ami.ml.post_processing.small_size_filter import SmallSizeFilterConfig

@admin.action(description="Run Small Size Filter post-processing task (async)")
def run_small_size_filter(self, request, queryset):
    if request.POST.get("confirm"):
        form = SmallSizeFilterActionForm(request.POST)
        if not form.is_valid():
            return _render_confirmation(request, queryset, form)
        cfg = form.to_config()
        jobs = []
        for collection in queryset:
            try:
                validated = SmallSizeFilterConfig(
                    **cfg,
                    source_image_collection_id=collection.pk,
                )
            except pydantic.ValidationError as exc:
                self.message_user(request, f"Bad config for collection {collection.pk}: {exc}", level="error")
                continue
            job = Job.objects.create(
                name=f"Post-processing: SmallSizeFilter on Capture Set {collection.pk}",
                project=collection.project,
                job_type_key="post_processing",
                params={"task": "small_size_filter", "config": validated.dict()},
            )
            job.enqueue()
            jobs.append(job.pk)
        self.message_user(request, f"Queued Small Size Filter for {len(jobs)} capture set(s). Jobs: {jobs}")
        return None

    return _render_confirmation(request, queryset, SmallSizeFilterActionForm())


def _render_confirmation(request, queryset, form):
    return TemplateResponse(
        request,
        "admin/post_processing/confirmation.html",
        {
            **self.admin_site.each_context(request),
            "title": "Run Small Size Filter",
            "task_label": "Small Size Filter",
            "form": form,
            "selected_count": queryset.count(),
            "selected_pks": [str(o.pk) for o in queryset],
            "action_name": "run_small_size_filter",
            "submit_label": "Run Small Size Filter",
            "changelist_url": reverse("admin:main_sourceimagecollection_changelist"),
            "model_meta": self.model._meta,
            "opts": self.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )
```

`_render_confirmation` is a module-private helper near the action; not a class method on the admin site. If a future PR finds itself duplicating it across admins, lift it to `ami/ml/post_processing/admin/helpers.py` then.

## Tests

All four test files live under `ami/ml/post_processing/tests/`. New tests do not touch the existing `ami/ml/tests.py` file (which holds older post-processing smoke tests).

**`test_base_schema.py`:**
- Subclassing without `config_schema` raises `TypeError`
- Bad config dict raises `pydantic.ValidationError` at task construction
- Valid config builds task, `task.config` is a `BaseModel` instance
- Unknown keys rejected (`extra="forbid"` semantics)

**`test_admin_form.py`:**
- `BasePostProcessingActionForm.to_config()` returns dict matching `cleaned_data`
- `SmallSizeFilterActionForm` validates `size_threshold` in `(0, 1)` exclusive
- Form errors render in confirmation template (smoke render via Django test client)

**`test_small_size_filter_admin.py`:**
- GET-equivalent (POST without `confirm`) renders intermediate page; no Job created
- POST with valid `confirm=yes` + `size_threshold=0.001` creates Job per collection with that threshold in `params['config']`
- POST with `size_threshold=2.0` re-renders form with error; no Job
- Multi-collection POST creates one Job per collection, each with correct project FK

Existing `SmallSizeFilterTask` behavior tests (in `ami/ml/tests.py`, if any) should still pass — schema validation is additive, default value preserved.

## Rebase Impact

### PR #1272 (tracking)

Net change: smaller diff.

- `ami/ml/post_processing/admin_forms.py` → `ami/ml/post_processing/admin/tracking_form.py` (location move)
- `TrackingActionForm` extends `BasePostProcessingActionForm`, gains `to_config()` override that drops empty `feature_extraction_algorithm_id`
- `tracking_confirmation.html` extends new shell + overrides `{% block intro %}` for "you are about to run tracking on N events…" preamble
- New `TrackingConfig(pydantic.BaseModel)` schema replaces freeform dict; `tracking_task.py` reads typed `self.config`
- Admin actions in `ami/main/admin.py` reuse new template via `_render_confirmation` helper (or its lifted version)
- Per-project Job partitioning loop stays in #1272 (this PR doesn't ship the helper)

Coordination: I (current author) own both #1272 and the precursor, so this rebase is internal.

### PR #999 (class masking)

Net change: smaller diff, but bigger lift than #1272 because #999 used hand-rolled HTML.

- Hand-rolled `<select name="taxa_list">` / `<select name="algorithm">` HTML → `ClassMaskingActionForm(BasePostProcessingActionForm)` with `ModelChoiceField(queryset=TaxaList.objects.…)` + `ModelChoiceField(queryset=Algorithm.objects.…)`
- `class_masking_confirmation.html` becomes thin override of new shell with masking-specific intro/preview block
- New `ClassMaskingConfig` + `RankRollupConfig` schemas
- Admin action validates form + builds typed config via `to_config()` instead of pulling from `request.POST` directly

Coordination: post-merge of precursor PR, message mohamedelabbas1996 in PR #999 with rebase guidance + concrete diff suggestions. Their existing rank-rollup work is unaffected; only the class-masking trigger needs reshaping.

## Risks

1. **Pydantic v1 vs v2 mismatch.** Container is v1 (per memory `MEMORY.md`: "Container uses Pydantic v1 — use `.dict()` / `.json()`, not `.model_dump()` / `.model_dump_json()`"). Spec uses v1 syntax throughout. CI runs in container, so v1 is enforced.

2. **`__init_subclass__` strictness change.** Adding `config_schema` to required attrs breaks any out-of-tree subclass. Only in-tree consumers exist; check shows: `SmallSizeFilterTask` (will be migrated in this PR), and the `BasePostProcessingTask` referenced in #1272 + #999 (rebase territory). Acceptable.

3. **Pydantic `BaseModel` in `Job.params['config']`.** Stored as dict via `validated.dict()`. JSONField round-trip is lossless for primitive-typed schemas. Risk: if a future schema uses `datetime` or non-JSON-native types, serialization needs explicit `.json()` → `json.loads(...)` round-trip. Out of scope for this PR (small-size-filter has only `int` + `float`).

4. **Test runner uses `--keepdb`.** Existing `test_ami` DB has prior `SmallSizeFilterTask` migration. New tests don't add migrations. Should pass cleanly; verify with `docker compose -f docker-compose.ci.yml run --rm django python manage.py test ami.ml.post_processing.tests --keepdb`.

5. **Form action POST vs GET ergonomics.** Django admin actions are POST-only. The "render confirmation page" leg uses POST without `confirm` flag. Existing pattern in #1272 + #999. No new risk.

## Out of Scope (Future Work)

- **Project-partitioning helper** (`enqueue_post_processing_jobs(queryset, task_cls, cleaned_data, scope_resolver)`). Belongs in whichever multi-scope adopter lands first (likely #1272, since tracking partitions; #999's masking is single-Occurrence-scoped per row).
- **REST API surface** for triggering post-processing from UI. Eventual replacement for admin trigger as primary surface.
- **Schema-driven form generation** (auto-build a `ModelForm`-style form from a pydantic schema). Tempting but premature; current task count = 1, second adopter has scope-aware dropdowns that don't fit auto-generation.
- **Job param schema versioning.** Once multiple post-processing tasks ship and config schemas evolve, a `schema_version` field on the schema may be needed for backward-compat with old Job rows. Defer until first breaking schema change.

## Implementation Plan

To be drafted by writing-plans skill after user approves this spec.
