# Safe live testing on shared dev DB — `atomic()` + rollback sentinel

Pattern for exercising mutating code paths (`save_results`, `create_detections`, etc.) against the real dev-server database without leaving state behind. Useful when:

- The unit test suite can't reproduce a specific bug because it uses fakes/factories
- You need to exercise a code path with real upstream data (image rows, algorithm rows, etc.) that you don't want to fabricate
- You don't have permission (or shouldn't) to delete pre-existing rows on the shared DB

## The pattern

```python
from django.db import transaction

class _Rollback(Exception):
    pass

try:
    with transaction.atomic():
        # call the mutating code under test
        save_results(results, job_id=None)

        # observe state INSIDE the atomic block (writes are visible here)
        for s in images:
            s.refresh_from_db()
            print(s.detections.count(), s.detections.filter(NULL_FILTER).count())

        # …assertions…

        raise _Rollback("intentional rollback to keep DB clean")
except _Rollback:
    pass

# after the block: DB restored to baseline
```

## Why a custom exception, not just `transaction.set_rollback(True)`?

- `set_rollback(True)` is silent — easy to forget and accidentally let writes commit. Custom exception is loud.
- A bare `raise` would propagate. The `_Rollback` class lets us catch *only* the intentional rollback and let real errors bubble.
- Inside the `try/except`, exceptions from the code under test (e.g. a `RuntimeError` from `create_classifications`) still propagate normally — separate the failure-injection signal from the cleanup signal.

## How to run a multi-line script in the Django container

`docker compose exec -T django python -c "..."` does NOT work for Django code — Django's app registry isn't loaded for raw `python -c`. You get `AppRegistryNotReady: Apps aren't loaded yet.`

Two options that DO work:

```bash
# Option A: stdin into manage.py shell (good for one-shot scripts)
docker compose exec -T django python manage.py shell < /path/to/script.py

# Option B: copy file in, then run (good if you want logs / args)
docker cp /tmp/script.py container-name:/tmp/script.py
docker compose exec -T django python manage.py shell -c "exec(open('/tmp/script.py').read())"
```

For testing on a remote dev box, the canonical flow is:

```bash
scp /tmp/script.py antenna-dev-serbia:/tmp/script.py
ssh antenna-dev-serbia 'docker cp /tmp/script.py antenna-django-1:/tmp/script.py && \
  cd ~/antenna && docker compose exec -T django python manage.py shell < /tmp/script.py'
```

## Example: validating PR #1312 `save_results` fix

Full scripts in `docs/claude/sessions/2026-05-19-pr-1312-premptive-processed-marker.md`. The pattern lets you:

- Build a synthetic `PipelineResultsResponse` (mix of images with/without detections)
- Call `save_results` and observe `Detection.bbox`, `Detection.occurrence_id`, `Occurrence.determination_id`
- Inject a downstream failure via `unittest.mock.patch("ami.ml.models.pipeline.create_classifications", side_effect=RuntimeError(...))`
- Roll back everything, leaving the shared DB unchanged

## Caveats

- **Side effects outside the transaction will NOT roll back.** Examples on this codebase:
  - `transaction.on_commit(lambda: task.delay())` Celery dispatches
  - `update_calculated_fields` background tasks
  - S3 / MinIO writes
  - Cache invalidations via signals that don't honor transactions

  For `save_results`, `transaction.on_commit` callbacks won't fire on rollback, which is usually what you want (no spurious downstream work). But if the code under test writes to external systems, those writes persist.

- **`refresh_from_db()` is required** to see in-block changes on objects you fetched before the mutation — Django's in-memory objects don't auto-sync.

- **Don't use this pattern for irreversible operations** (deleted-then-recreated unique constraints, sequence advances). Postgres sequences advance even on rollback.

- **Auto-mode classifier may still block destructive verbs** (`DELETE`, `.delete()`) even when wrapped in `atomic()`, because the classifier reads the statement intent, not the transaction surroundings. If blocked, either ask the user explicitly or restructure to avoid the destructive verb.
