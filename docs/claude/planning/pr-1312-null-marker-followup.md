# PR #1312 follow-up — null-marker abstraction + move-to-end + cleanup

Created 2026-05-20. Builds on existing branch `fix/premptive-processed-marker`.

Splits remaining work from the takeaway review of PR #1312 into two PRs.

## PR-A (this plan): move null to end + null-detection abstraction + project 171 cleanup

Extends PR #1312. Adds commits on top of the existing `4e33f96` ordering fix.

### Scope rationale

Current PR moves null markers AFTER real detection / classification / occurrence saves but BEFORE `source_image.save()` loop, `create_detection_images.delay()`, `update_calculated_fields_for_events`, and `Deployment.update_calculated_fields`. Per Copilot's review: any raise in those four steps still leaves a null marker persisted while the function failed.

PR-A closes that window by moving null persistence to the absolute final step. Failure window left = the return statement — effectively zero.

Bundled because all changes touch the same call graph (`save_results` body + `Detection` manager + `OccurrenceQuerySet.valid()` + cleanup of the rows the bug produced). Reviewing them together gives a single coherent semantic for what "null marker" means going forward.

### Final order in `save_results`

1. `create_detections(real_responses, ...)`
2. `create_classifications(...)`
3. `create_and_update_occurrences_for_detections(...)`
4. `source_image.save()` loop
5. `create_detection_images.delay(...)`
6. `update_calculated_fields_for_events(pks=event_ids)`
7. `Deployment.update_calculated_fields(save=True)` loop
8. `create_detections(null_responses, ...)` ← was step 0, now last write
9. return

### Null-detection abstraction

`ami/main/models.py`:

```python
class Detection(BaseModel):
    NULL_BBOX = None  # canonical sentinel value for new rows

    @property
    def is_null_marker(self) -> bool:
        return self.bbox is None or self.bbox == []

    @classmethod
    def build_null_marker(cls, source_image, detection_algorithm) -> "Detection":
        return cls(
            source_image=source_image,
            bbox=cls.NULL_BBOX,
            detection_algorithm=detection_algorithm,
            timestamp=now(),
        )


class DetectionQuerySet(BaseQuerySet):
    def valid(self):
        """
        Detections suitable for consumer queries — excludes null-marker sentinels.
        Future predicates to fold in here: soft-delete tombstones, missing
        detection_algorithm, missing classifications.
        Consumers asking 'give me detections' should always go through .valid().
        """
        return self.exclude(NULL_DETECTIONS_FILTER)

    def null_markers(self):
        """
        Sentinel rows recording 'this algorithm ran against this image and
        found nothing.' Only for SourceImage-level 'has this been processed?'
        questions. Detection consumers should use .valid() instead.
        """
        return self.filter(NULL_DETECTIONS_FILTER)
```

Rename existing `DetectionQuerySet.null_detections()` (`ami/main/models.py:2721`) → `null_markers()`. Single sweep across codebase.

### Call-site sweep

`.exclude(NULL_DETECTIONS_FILTER)` → `.valid()`:
- `ami/main/models.py:817, 1229, 2037, 2243`
- `ami/main/api/views.py:614, 913`
- `ami/ml/models/pipeline.py:99, 103`

`.filter(NULL_DETECTIONS_FILTER)` → `.null_markers()`:
- `ami/main/models.py:2722` (the method itself, becomes the body of `null_markers()`)

Drifted inline at `ami/main/models.py:4108` (`~Q(...bbox__isnull=True) & ~Q(...bbox=[])`) → rewrite to use `.valid()` via subquery or join-based predicate. Verify it still works against ORM aggregation.

Inline `bbox__isnull=True` at `ami/ml/models/pipeline.py:454-458` — intentional (only `IS NULL` form, comment explains). Leave alone but add a one-line comment pointing readers to `Detection.NULL_BBOX` for the canonical sentinel.

### Occurrence valid() tightening

`OccurrenceQuerySet.valid()` at `ami/main/models.py:2913` currently only excludes `detections__isnull=True`. Extend to also exclude:
- Occurrences whose only detections are null markers
- Occurrences with `determination__isnull=True`

Use new `Detection.objects.valid()` helper to express "has at least one valid detection."

### Project 171 cleanup

Management command `ami/main/management/commands/cleanup_null_only_occurrences.py`:
- For each Occurrence in given project with no `Detection.objects.valid()` rows: delete the Occurrence and its null-marker Detection rows
- Source images then re-yield from `filter_processed_images` on next pipeline run
- Idempotent: re-running on a cleaned project is a no-op
- Dry-run mode by default

### TDD test plan

Tests added to `ami/ml/tests.py::TestPipeline` (extends the two already added in `4e33f96`):

1. **Broker outage path** — patch `create_detection_images.delay` to raise `OperationalError`. Assert:
   - `RuntimeError`/`OperationalError` propagates
   - Zero null markers on the undetected image
   - `filter_processed_images` yields the image on a second run

2. **Calc-field DB error path** — patch `update_calculated_fields_for_events` to raise. Same assertions as #1.

3. **`Detection.is_null_marker` property** — direct property test for both `bbox=None` and `bbox=[]` legacy form.

4. **`Detection.objects.valid()` and `.null_markers()`** — assert disjoint querysets covering full Detection set for a fixture image with one real + one null detection.

5. **OccurrenceQuerySet.valid() exclusion** — fixture with three occurrences: real detection only / null detection only / null determination. Assert `valid()` returns only the first.

6. **Cleanup management command dry-run** — fixture project with phantom occurrences. Run command with `--dry-run`. Assert reported counts match. Run without dry-run. Assert deletion.

### Commit shape

Roughly:
1. `test(ml): RED test for broker-outage leaving null marker`
2. `fix(ml): move null-marker creation to final step in save_results`
3. `refactor(main): add DetectionQuerySet.valid()/.null_markers() + Detection.is_null_marker + build_null_marker`
4. `refactor(main): sweep call sites to use .valid() / .null_markers()`
5. `fix(main): tighten OccurrenceQuerySet.valid() to exclude null-only and null-determination`
6. `feat(main): cleanup_null_only_occurrences management command`

### Out of scope for PR-A

- `transaction.atomic()` + `transaction.on_commit` wrap — see PR-B below
- Re-classification gap in `filter_processed_images` — separate ticket
- `bbox = '[]'` legacy data migration — `NULL_DETECTIONS_FILTER` absorbs it; rewrite is unnecessary churn

## PR-B (follow-up): narrow transaction.atomic() + on_commit

After PR-A merges. Tracked at `docs/claude/planning/pr-1312-tx-wrap-followup.md` (to be written).

Wraps `create_detections` + `create_classifications` + `create_and_update_occurrences_for_detections` + final `create_detections(null_responses, ...)` in `transaction.atomic()`. Dispatches `create_detection_images.delay` via `transaction.on_commit`. Calc-field updates stay outside.

Closes the narrow "real detection committed but classification failed mid-bulk-create" window that PR-A leaves open. Separate PR because tx changes carry concurrency risk (PR-1261 scar) — needs its own multi-worker contention e2e plan and clean revert path.

## E2E validation plan (PR-A)

Reusing the dev-box atomic-rollback testing pattern from the previous session:

1. Happy path: full async_api job. Assert no new phantom occurrences, all real detections persist, null markers on undetected images persist.
2. Broker-outage simulation: kill RabbitMQ mid-job or patch `delay()` to raise. Assert image stays in `filter_processed_images` yield list.
3. Calc-field DB error: patch `update_calculated_fields_for_events` to raise. Same assertion.
4. Cleanup command: run dry-run on project 171, capture counts, run for real, assert API no longer returns null-only Occurrences.
