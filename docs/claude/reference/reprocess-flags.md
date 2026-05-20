# Reprocess flags — how `reprocess_all_images` and `reprocess_existing_detections` interact

Two flags govern whether an ML job re-runs over already-processed images. They look similar but control different stages and interact in non-obvious ways. Source of truth: `ami/ml/models/pipeline.py:140-253`.

## The two flags

| Flag | Where it lives | What it controls |
|---|---|---|
| `reprocess_all_images` | Per-job kwarg; also `Project.feature_flags.reprocess_all_images` | Whether `filter_processed_images` runs at all on the collected images |
| `reprocess_existing_detections` | `Project.feature_flags.reprocess_existing_detections` + optional `pipeline_config["reprocess_existing_detections"]` | Whether existing `Detection` rows are sent to the pipeline as `DetectionRequest`s (so the pipeline re-classifies them) instead of being recreated |

## The collect step (`collect_images`, lines 134-176)

- `reprocess_all_images=False` (default): `filter_processed_images(images, pipeline)` filters out images that have already been processed by the pipeline's algorithms. Only images that need work are sent.
- `reprocess_all_images=True`: filter is bypassed; every image in the collection goes downstream regardless of prior state.

## The process step (`process_images`, lines 179-253)

`process_images` re-runs the filter (line 212) unless `reprocess_all_images=True`. So the filter actually runs twice in the default path — once on collect, once before dispatch.

Then a separate decision (lines 232-237):

```python
reprocess_existing_detections = reprocess_all_images
if project and project.feature_flags.reprocess_existing_detections:
    if pipeline_config.get("reprocess_existing_detections", True):
        reprocess_existing_detections = True
```

When `reprocess_existing_detections` is true, the existing `Detection` rows for each image are bundled into the request as `DetectionRequest`s. The pipeline then re-classifies those same bboxes rather than redoing detection.

## What you observe when only `reprocess_all_images=True`

- All collected images are sent to the pipeline (filter bypassed).
- BUT `reprocess_existing_detections` becomes `True` too (line 232), so existing detection rows are sent with them.
- The pipeline returns those same detections (often with updated classifications).
- `create_detections` in `save_results` matches incoming detections against existing rows by `(source_image, bbox, detection_algorithm)` and **updates in place** — no new `Detection` rows.
- Net effect: detection count and PKs unchanged after the job. **Do not interpret this as "save_results didn't run."** It did; it just didn't need to create new rows.

This is what was observed on serbia in PR #1312 e2e: project 9 had `reprocess_all_images=True`, job 162 reprocessed all 10 images, and the DB delta was zero because every detection was already there.

## What you observe when only `reprocess_existing_detections=True`

- `filter_processed_images` still skips fully-processed images.
- For images that DO need work (e.g. a new classifier was added), their existing real detections are sent to the pipeline as `DetectionRequest`s instead of being re-detected from scratch.

## What you observe when BOTH are off (the default)

- `filter_processed_images` skips fully-processed images.
- Surviving images go to the pipeline with NO existing detections in the request — the pipeline runs the detector from scratch and `create_detections` creates new rows.

## Implications for testing

- **For regression / behavior tests on `save_results`:** the unit tests already use synthetic `PipelineResultsResponse` objects, so flag state doesn't matter there.
- **For e2e tests on a dev box:** if you want to see `Detection` row count grow, you need `reprocess_all_images=False` AND images that are genuinely unprocessed by the target pipeline. Easiest way: pick a pipeline whose detector algorithm has not run on the images yet (different `detection_algorithm_id`), OR use a fresh `SourceImageCollection` whose images have never been processed.
- **For "I ran the job and nothing changed in the DB" debugging:** check the project's `feature_flags.reprocess_all_images` first. If it's on and `reprocess_existing_detections` is off, your job ran fine but performed updates in place. Use celeryworker logs (`Saved pipeline results to database with N detections`) for evidence of activity.

## `test_ml_job_e2e` reported stats are pipeline-response counts, not DB delta

`manage.py test_ml_job_e2e` prints lines like:

```
📊 Final Results:
  Process: 100.0% (SUCCESS)
    Processed: 10
  Results: 100.0% (SUCCESS)
    Captures: 10
    Detections: 68
    Classifications: 121
```

"Detections: 68" is the number of `DetectionResponse` objects returned by the pipeline across all batches in this job. It is NOT the number of new rows in the `Detection` table. If `reprocess_existing_detections` is true and the pipeline returned the same bboxes, you can see "Detections: 68" with zero net DB changes.

For DB-delta verification, snapshot detection / occurrence PKs before and after via Django shell, not via job stats.
