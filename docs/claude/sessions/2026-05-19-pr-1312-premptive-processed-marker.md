# PR #1312 — fix preemptive null-detection marker (Issue #1310)

Created 2026-05-19. Branch: `fix/premptive-processed-marker`. URL: https://github.com/RolnickLab/antenna/pull/1312

## Status

- ✅ PR opened against `main`
- ✅ TDD: 2 new failing tests added (`ami/ml/tests.py::TestPipeline`), then code fix made them pass
- ✅ Local test suites: `ami.ml.tests` + `ami.jobs.tests` = 170/170 pass; 18/18 in `TestPipeline`
- ✅ Manual e2e on serbia dev server (2026-05-19) — 3 paths validated, see below

## Bug

Issue #1310: project 171 had ~400 captures marked as processed with only null-bbox detections, no real detections, and phantom Occurrences with `determination=NULL` leaking to API.

Root cause in `ami/ml/models/pipeline.py::save_results` (pre-fix order):
1. `create_null_detections_for_undetected_images` ran FIRST, built null `DetectionResponse`s for images with no real detections
2. Null responses merged into `results.detections` (`results.detections = results.detections + null_detections`)
3. `create_detections` bulk-saved the merged list (null + real)
4. `create_classifications` and `create_and_update_occurrences_for_detections` then iterated **all** detections — including nulls — so each null spawned an Occurrence with `determination=NULL`

Failure mode: any exception in steps 3-4 left the image with a null marker already in DB but no real detections + phantom Occurrences. `filter_processed_images` then permanently skipped these images.

## Fix (PR #1312)

`ami/ml/models/pipeline.py::save_results`:
- Real `create_detections` / `create_classifications` / `create_and_update_occurrences_for_detections` run first on real DetectionResponses only
- THEN `create_null_detections_for_undetected_images` builds null responses, passed to a SECOND `create_detections` call
- Nulls never enter the classification or occurrence loops → no phantom Occurrences even on happy path
- If any earlier step raises, null markers are never persisted → `filter_processed_images` re-yields the image on retry

## Tests added

`ami/ml/tests.py::TestPipeline`:
- `test_null_detection_does_not_create_phantom_occurrence` (line ~1028) — happy path: pipeline finds nothing, null marker created, no Occurrence
- `test_captures_not_marked_processed_after_failure` (line ~1054) — patches `create_classifications` to raise; asserts no null marker persisted, `filter_processed_images` re-yields image

Both tests confirmed RED against pre-fix code, GREEN after fix.

## Verified safe (during brainstorm)

Skipping Occurrence creation for null detections is safe because:
- `Detection.occurrence` FK is `null=True, on_delete=SET_NULL` (`ami/main/models.py:2764-2770`)
- Tracking not yet implemented — `create_and_update_occurrences_for_detections` carries `@TODO remove when we implement tracking!` comment
- All `Detection.objects.filter(occurrence=…)` traversals start FROM an Occurrence; never traverse from a null detection
- `create_classifications` loops paired responses; null DetectionResponses have empty `.classifications` → never iterated
- `seed_synthetic_occurrences` already excludes `occurrence__isnull=True`

## Out-of-scope follow-ups (in PR body)

1. **API filter for null-only / no-determination occurrences.** `OccurrenceQuerySet.valid()` (`ami/main/models.py:2913-2914`) currently only excludes `detections__isnull=True`. Doesn't exclude null-only-detection occurrences or `determination__isnull=True`. With this PR no new phantom Occurrences will be created, but project 171's existing phantoms still surface via API until `valid()` is tightened or `OccurrenceViewSet.get_queryset` (`ami/main/api/views.py:1220-1238`) adds the exclusion.

2. **Cleanup of project 171's broken state.** ~400 source images have null-only detections + phantom Occurrences. Need management command to delete null-only Detection rows + their phantom Occurrences so `filter_processed_images` re-processes them.

3. **TODO ticket: re-classification gap.** `filter_processed_images` notes "we don't yet have a mechanism to reclassify detections" — current behavior is to reprocess from scratch. Not blocking but worth tracking.

## E2E results (serbia dev box, 2026-05-19)

Serbia originally on `copilot/implement-option-a-job-logs`. Fetched + checked out `fix/premptive-processed-marker`, restarted django + celeryworker, confirmed reordered `save_results` loaded via `inspect.getsource`. After testing, restored to original branch.

### Path 1: happy path — async_api job (full stack)

Triggered via `manage.py test_ml_job_e2e --project 9 --collection 38 --pipeline quebec_vermont_moths_2023 --dispatch-mode async_api`. Job 162 succeeded in 44s. NATS path, 10 images, 8 save_results batches. Detection / occurrence counts unchanged (project 9 has `reprocess_existing_detections=False`, so existing rows were not duplicated). No new phantom occurrences.

### Path 2: zero-detection path — synthetic save_results inside atomic

Live script `/tmp/test_save_results_live.py` (copied into django container). Built a `PipelineResultsResponse` with two source images: 173110 (one bbox detection) and 173740 (no detection in `results.detections`). Called `save_results` inside `transaction.atomic()` with explicit rollback at end.

In-flight state observed:
- si=173110: 1 new real detection + pre-existing pristine null det (52287 → pre-existing phantom occ 52073)
- si=173740: 1 new null marker (det 61357, `bbox=None`, `occurrence_id=None`)
- New phantom occurrences (excluding pre-existing 52073): **0**

Post-rollback: baseline restored.

### Path 3: failure path — patch `create_classifications` to raise

Live script `/tmp/test_failure_path.py`. Same `PipelineResultsResponse` as path 2, but wrapped `save_results` call in `patch("ami.ml.models.pipeline.create_classifications", side_effect=RuntimeError(...))`. Confirmed RuntimeError propagates up out of `save_results`. In-flight state:
- si=173110: 1 new real detection created (create_detections ran before classification raised)
- si=173740: **0 new null markers** — `create_null_detections_for_undetected_images` never ran because the exception fired before it.

This confirms the core fix: image without real detections stays unmarked when downstream save fails, so `filter_processed_images` will re-yield it on retry.

### Same `save_results` is shared by v1 sync + v2 async (NATS)

Confirmed: path 1 was async_api (NATS), but the function under test is identical for sync_api too. Single e2e on either dispatch path validates both.

## Files touched

- `ami/ml/models/pipeline.py` — `save_results` body reordered, +null_detection_responses path
- `ami/ml/tests.py` — Occurrence import + 2 new tests

## Compose gotcha (worth remembering)

For tests on main repo while a worktree override is active in `docker-compose.override.yml`, use `docker-compose.ci.yml` which doesn't pull the override (only mounts `.:/app:z` from current directory). The local dev stack will read the bound worktree subdir instead of the main repo.

Stash trap encountered: `git stash` on the main repo branch did NOT stash uncommitted edits to `ami/ml/tests.py` + `ami/ml/models/pipeline.py` cleanly during a baseline-verification run. Edits were lost on `stash pop`. Workaround: don't stash to compare against baseline; instead run the test pre-edit on a clean checkout, or `git diff` the file directly.
