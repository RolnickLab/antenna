# Merge plan: tracking stack, retraining PR and the model-outputs phases

Date: 2026-10-01. Companion to `2026-10-02-model-outputs-and-review-design.md` (section 10
phases, section 11 split). PR states checked on this date.

## Where the stack is

| PR | Base | State | Notes |
|---|---|---|---|
| #1272 tracking as a post-processing task | `main` | open, changes requested, one failing check | the root of the stack; carries main migrations 0096–0101 and the pgvector extension migration |
| #1432 track review UI | #1272 | open | UI only; no CI until retargeted to `main` |
| #1439 embeddings + occurrence history + timeline | #1432 | **draft, conflicting with its base** | to be split, not rebased |
| #1442 tracking cost terms and tuning | #1439 | draft | needs link cost on `Detection` and candidate files |
| #1444 undo tracking for a session | #1442 | draft | |
| #1407 retrain a classifier head | `main` | open, review required, **conflicting with main** | second `DetectionEmbedding`, `ml/0029`, `main/0096–0099` |
| #1423 model performance UI | `main` | draft | the UI half of #1407 |

CI runs backend tests only on PRs based on `main`, so every stacked PR is untested until it is
retargeted. That is the main schedule risk and the reason to land the root quickly.

## Order

1. **#1272 lands first.** Address the requested changes and the failing check; relax the
   `ClassificationResponse.features` validator from "exactly 2048" to drop-and-warn (a 1,024-d
   BioCLIP vector must not fail the whole batch). Operations before it deploys: the pgvector
   extension installed at 0.8.x on production and staging (the compose image already installs
   0.8.*; managed databases are a separate step), since its migration creates the extension and
   phase 1 will create a `halfvec` column.
2. **#1432 retargets to `main`** the moment #1272 merges, gets its first CI run, lands.
3. **Phase 1 PR, new, from `main`**: the embeddings foundation carved from #1439 (commit list in
   the design note, section 11): abstract `AlgorithmOutput` and `Embedding`,
   `DetectionEmbedding(detection, algorithm, job, project, key, vector halfvec)`, `job` on
   `Classification` and `Detection`, `Algorithm.feature_extractor`, the box-matched writer, the
   feature-only job, the reader module, tracking and merge ranking reading it, the
   `Classification` docstring. Migrations rewritten: `main/0102` creates the table in its final
   shape (and drops a `DetectionEmbedding` left by an earlier draft on any development database);
   #1439's `0104` repair and `ml/0029 embedding_dimensions` fold in. This PR is based on `main`
   and gets CI.
4. **#1407 rebases onto `main` + phase 1.** It drops `ami/ml/models/embedding.py`, its
   `ml/0029`, the positional writer, `EMBEDDING_DIMENSIONS`, the `store_classification_embeddings`
   flag and `GenerateEmbeddingsJob`; reads `DetectionEmbedding.objects.filter(algorithm=
   head.feature_extractor, key="embedding")`; renumbers `main/0096–0099` and `ml/0030–0033`
   after phase 1's; moves `training_info.job_id` out of `ami/ml/schemas.py`. Then #1423.
5. **Phase 2 PR, new, from `main`**: `AlgorithmResult` and `ValidationReview` from #1439's
   history commits, `Job.hidden` and `Job.algorithms`, the history endpoint and the timeline UI.
   Depends on #1432 for the review UI pieces, so it lands after step 2. **#1439 closes** once
   steps 3 and 5 are open, with a comment pointing at both.
6. **#1442 rebases onto phase 2** (its base today is #1439). It writes `next_detection_cost` and
   `next_detection_job` on `Detection` and its candidate matrices to a file per job, and tunes
   against `ValidationReview(aspect=grouping)`. **#1444 rebases onto #1442.**
7. **Phase 3 PR** (result files) proceeds in parallel after step 3; it touches the processing
   service contract and `Classification`, not the tracking code.

Processing-service side: the features-for-all-detections PR lands before the BioCLIP classifier
PR, and the classifier emits its backbone vector in `detections[].embeddings` under the
extractor's key.

## Migration numbering

`main` is at `main/0095`, `ml/0028`, `jobs/0023`. #1272 takes `main/0096–0101`. Phase 1 takes
`main/0102` (+ `ml/0029` for `feature_extractor`). #1407 renumbers behind those. Development
databases that applied an earlier `main/0102` or #1407's `ml/0029` need `migrate --fake` or a
drop of the old table; the phase 1 migration handles the table drop, not the migration history.

## What each tracking session must change in its branches

- Any code on #1439 / #1442 / #1444 that imports `DetectionEmbedding` keeps the name; the
  fields it uses gain `job`, `project` and `key`, and the column type changes to `halfvec`. The
  reader `models_future/embeddings.py` keeps its functions; `vectors_for_detections` gains a
  `key` argument defaulting to `"embedding"`.
- `OccurrenceHistoryRecord` becomes `AlgorithmResult` with `project`, three nullable targets,
  `value`, `is_current`; its `kind=review` rows become `ValidationReview`. Writers call
  `AlgorithmResult.objects.record(...)`.
- `record_tracking_determination` stays as is. `TrackingHistory.link_costs` becomes the write
  of `next_detection_cost` plus the candidate file.
- Jobs are soft-deleted; nothing may hard-delete a job that has outputs.

## Risks

- #1272's review state and failing check are the critical path; nothing stacked can get CI
  before it lands.
- Two drafts (#1439, #1407) both carry a `DetectionEmbedding`; whichever is cherry-picked
  second must drop its copy, or the migration graph forks in two apps.
- The pgvector extension version on managed databases is an operations task that gates phase
  1's `halfvec` column; confirm before opening the phase 1 PR for review.
