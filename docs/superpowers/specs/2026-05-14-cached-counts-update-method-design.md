# Cached counts: `update_cached_counts` method design

**Date:** 2026-05-14
**Context:** Follow-up to PR #1301 takeaway-review feedback. Replace per-source-table dedup state + per-model Celery refresh tasks with a generic instance/queryset method that wraps `update_calculated_fields(save=True)`.

## Goals

1. Single source of truth for "recompute and persist this row's cached counts" across the codebase.
2. Caller-controlled sync vs async (`run_async=True` default).
3. Per-(model, pk) dedup so high-volume signal fan-out collapses to one task per affected row, regardless of how many source-row writes triggered it.
4. No new concepts at the field declaration site: `CachedCountField` marker, model `update_calculated_fields` body, and the periodic reconcile task stay as-is.

## Non-goals

- Declarative `invalidate_on=[Detection, ...]` on field. Deferred to follow-up; the registry would sit on top of this method.
- Plugging the bulk_create / bulk_update / raw-SQL blind spot. That stays the responsibility of `reconcile_cached_counts_task` and inline calls in ML worker code (`pipeline.save_results`).
- Splitting `update_calculated_fields` into "just counts" vs "derived state (S3 sums, first/last timestamps)". Wrapper stays thin today; semantic split is a separate concern when refreshing one drift forces a full S3 scan and we notice.

## Architecture

### New module: `ami/base/cached_counts.py`

Per-connection dedup set keyed by `(model_label, pk)`. One `transaction.on_commit` hook per connection drains the set and dispatches the generic Celery task once per unique `(model_label, pk)`.

```python
_PENDING_ATTR = "_pending_cached_count_recomputes"

def _schedule_recompute(model: type[models.Model], pk: Any) -> None:
    pending = getattr(connection, _PENDING_ATTR, None)
    is_new = pending is None
    if is_new:
        pending = set()
        setattr(connection, _PENDING_ATTR, pending)
    pending.add((model._meta.label, pk))
    if is_new:
        # Outside an atomic block, on_commit fires synchronously at
        # registration time — the add above must precede it.
        transaction.on_commit(_flush_pending_recomputes)


def _flush_pending_recomputes() -> None:
    pending = getattr(connection, _PENDING_ATTR, set())
    try:
        delattr(connection, _PENDING_ATTR)
    except AttributeError:
        pass
    for label, pk in pending:
        recompute_cached_counts_task.delay(label, pk)


@shared_task(ignore_result=True)
def recompute_cached_counts_task(model_label: str, pk: Any) -> None:
    model = apps.get_model(model_label)
    try:
        instance = model.objects.get(pk=pk)
    except model.DoesNotExist:
        return
    instance.update_calculated_fields(save=True)
```

### `BaseModel.update_cached_counts(run_async=True)`

```python
class BaseModel(models.Model):
    def update_cached_counts(self, run_async: bool = True) -> None:
        if run_async:
            _schedule_recompute(type(self), self.pk)
            return
        self.update_calculated_fields(save=True)
```

### `BaseQuerySet.update_cached_counts(run_async=True)`

```python
class BaseQuerySet(QuerySet):
    def update_cached_counts(self, run_async: bool = True) -> None:
        for pk in self.values_list("pk", flat=True):
            if run_async:
                _schedule_recompute(self.model, pk)
            else:
                self.model.objects.get(pk=pk).update_calculated_fields(save=True)
```

## Call site changes

### `ami/main/signals.py`

Detection post_save/post_delete handler:

```python
@receiver(post_save, sender=Detection)
@receiver(post_delete, sender=Detection)
def update_collection_counts_on_detection_change(sender, instance, **kwargs):
    if not instance.source_image_id:
        return
    SourceImageCollection.objects.filter(images__id=instance.source_image_id).update_cached_counts()
```

m2m_changed on `SourceImageCollection.images.through`:

```python
@receiver(m2m_changed, sender=SourceImageCollection.images.through)
def update_collection_counts_on_m2m(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear"):
        instance.update_cached_counts()
```

Project default-filter cascade (stays hand-rolled; cascade is to children, not parents):

```python
def refresh_cached_counts_for_project(project: Project):
    Event.objects.filter(project=project).update_cached_counts()
    Deployment.objects.filter(project=project).update_cached_counts()
    SourceImage.objects.filter(project=project).update_cached_counts()
```

### `ami/main/tasks.py`

Drop `refresh_collection_cached_counts` entirely. `refresh_project_cached_counts` can also drop; the per-project cascade now schedules per-row tasks directly from the signal via the queryset method's `run_async=True` default. Reconcile task stays.

### `ami/main/checks/cached_counts.py` reconcile loop

```python
# before
instance.update_calculated_fields(save=True)
# after
instance.update_cached_counts(run_async=False)
```

Synchronous because reconcile already runs in a Celery task and we want the repair to complete before the result is reported.

### `ami/ml/models/pipeline.py` (worker context)

Stays as-is. Already runs in Celery and already dedupes via `.distinct()` on the collection queryset. Could optionally swap `collection.update_calculated_fields(save=True)` → `collection.update_cached_counts(run_async=False)` for stylistic unification — non-blocking on this PR.

## What goes away

- `_PENDING_SOURCE_IMAGE_IDS_ATTR` constant
- `_flush_pending_collection_refreshes` helper
- `_schedule_collection_refresh_for_source_image` helper
- `refresh_collection_cached_counts` task
- `refresh_project_cached_counts` task (its body becomes 3 queryset calls in the signal handler)

## What stays

- `CachedCountField` marker class
- Per-model `update_calculated_fields(save=True)` bodies (the actual recompute logic)
- Periodic `reconcile_cached_counts_task` and the integrity check module
- Inline calls in `pipeline.save_results` (worker-context, already deduped)

## Cost of adding the next cached count

Before: new field + recompute in `update_calculated_fields` + per-connection dedup attr + flush helper + Celery task + signal handler wiring (~6 things, ~50 LOC).

After: new field + recompute in `update_calculated_fields` + signal handler calling `.update_cached_counts()` (~3 things, ~10 LOC).

## Risks

1. **bulk_create / bulk_update skip signals.** Unchanged from current state. Reconcile task is the safety net. Cachalot accepts the same boundary at the SQL-compiler patch layer (raw cursor coverage is opt-in via `CACHALOT_INVALIDATE_RAW`).
2. **Project default-filter cascade fans out to thousands of children.** Today it's one task; under this design it becomes N small tasks. Net cost is slightly higher (more queue overhead) but each task is bounded and parallelizable. Separate issue from this PR.
3. **`update_calculated_fields` on Deployment does S3-sum + first/last timestamp work alongside the counts.** Refreshing drift on one count therefore triggers an S3 query. Acceptable today; flagged for future split.
4. **`async` is a Python reserved word.** Use `run_async` to match existing precedent (`process_single_source_image(run_async=True)`).

## Migration path

This PR (or a follow-up commit on PR #1301):

1. Create `ami/base/cached_counts.py` with `_schedule_recompute`, `_flush_pending_recomputes`, `recompute_cached_counts_task`.
2. Add `update_cached_counts` to `BaseModel` and `BaseQuerySet` in `ami/base/models.py`.
3. Refactor `ami/main/signals.py` — drop dedup helpers, switch handlers to queryset method.
4. Refactor `ami/main/tasks.py` — drop `refresh_collection_cached_counts` and `refresh_project_cached_counts`.
5. Update `ami/main/checks/cached_counts.py` reconcile loop.
6. Run existing tests in `ami/main/tests.py` (`test_source_image_cached_counts_refresh_on_threshold_change` etc.) to confirm parity.

## Tests

Existing tests cover:
- Threshold-change signal triggers refresh
- Detection post_save triggers per-collection refresh
- m2m_changed triggers refresh
- Bulk write drift is caught by reconcile

These should pass unchanged. One new test: per-connection dedup collapses N detection writes to ≤ N tasks, where N is the number of distinct affected target rows. (PR #1301 has the dedup test for the old code path; rewrite to assert against the new generic task.)
