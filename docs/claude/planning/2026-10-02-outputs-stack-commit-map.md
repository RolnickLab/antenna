# Model outputs stack: commit map for rebasing tracking onto it

Date: 2026-10-02. Audience: the session that rebases #1272 and #1432 onto the new stack.
Design: `2026-10-02-model-outputs-and-review-design.md` (sections 5.1, 5.3, 5.4, 5.6, 5.7, 7).

## The stack

```
main
 └─ A  feat/post-processing-results-history   results, reviews, job links, Job.hidden, history + timeline
     └─ B  feat/detection-embeddings-task      pgvector, DetectionEmbedding, feature-only jobs, "Add feature vectors"
         └─ C  claude/revive-tracking-feature-OyMO3 (#1272)  tracking backend, rebased onto B
             └─ D  feat/tracking-ui (#1432)                   tracking UI, rebased onto C
```

A and B hold nothing that only tracking uses. Everything tracking-specific from the two
source branches (`feat/embeddings-foundation` @01864b62 and `feat/algorithm-results-and-reviews`
@bcbc4233) moves into C or D as listed below. Neither A nor B has a PR yet.

| Branch | Head | Commits over its base |
|---|---|---|
| A | `aadc2dbc` | 0d3641bf results tables · 84aa6d47 Job.hidden · c31b1244 job and results on every write · 534c68d7 history endpoint + comments · 6deea96b timeline UI · 31ae6283 drop the grouping aspect · 506659b4 JSON config · aadc2dbc defer score arrays in history |
| B | `d824849d` | f0555ed1 pgvector · c5988b55 DetectionEmbedding · 304eb51e writers + feature-only path · 5074b208 "Add feature vectors" task · 39e38b8f docs · d824849d scope includes captures with no own project |

## Migrations after A and B

| App | A | B |
|---|---|---|
| main | `0096_algorithm_results_reviews_and_output_jobs` (AlgorithmResult, ValidationReview, Classification.job, Detection.job) | `0097_enable_pgvector_extension`, `0098_detection_embedding` |
| jobs | `0024_job_hidden_and_deployment_set_null` | (none) |
| ml | (none) | `0029_algorithm_embedding_dimensions` |
| exports | (none) | (none) |

### What C does with #1272's migrations

| #1272 file | Action in C | Why |
|---|---|---|
| `main/0096_add_pgvector_extension` | **Drop** | B's `main/0097_enable_pgvector_extension` creates the extension. Also drop #1272's `compose/local/postgres/Dockerfile` and `requirements/base.txt` pgvector hunks; B's are identical. |
| `main/0097_classification_features_2048` | **Drop** (recommended) | Tracking reads vectors from `DetectionEmbedding` through B's readers. If C keeps the column, renumber it to follow `main/0098_detection_embedding` and re-add the reader fallback itself (B has none). |
| `main/0098_detection_next_detection` | Renumber to `main/0099_…`, depend on `("main", "0098_detection_embedding")` | |
| `main/0099_occurrence_grouping_verification` | Renumber to `main/0100_…` | |
| `main/0100_occurrence_track_stats` | Renumber to `main/0101_…` | |
| `main/0101_grant_run_post_processing_to_ml_data_manager` | Renumber to `main/0102_…` | |
| (new) | Add `main/0103_validation_review_grouping_aspect` | A dropped `grouping` from `ValidationReview.Aspect`. C adds it back: an `AlterField` on `validationreview.aspect` choices (state only). |
| `exports/0002_add_tracks_csv_format` | Keep as is | `exports` has only `0001` on A and B. |

Migrations from the source branches that are obsolete and must not be carried: `main/0102_detection_embeddings_and_output_jobs`, `main/0103_algorithm_results_and_validation_reviews`, `jobs/0024_job_deployment_set_null`, `jobs/0025_job_hidden`, and the source `ml/0029` (B has its own with the same operations). Any database that applied them, or #1272's numbering, is rebuilt by replay as agreed in the design note; nothing upgrades in place. Run `makemigrations --check --dry-run` on C after renumbering.

## Commit map: `feat/embeddings-foundation` (over #1272 @b63a095b)

"B" means the change is in B already, usually rewritten; do not cherry-pick it again.

| Commit | Subject (short) | Now |
|---|---|---|
| f95b38d9 | store a vector for every detection the service sends | **B** (304eb51e: EmbeddingResponse, create_detection_embeddings). Its migration is obsolete. |
| 8ba13d66 | tracking + merge ranking read stored embeddings | **C**: merge_candidates.py, tracking_task.py, admin_forms.py, tracking tests in ami/main/tests.py, the serializer hunk, the `count_valid` and old `has_vector` model hunks. The reader module itself is in B (c5988b55/304eb51e) without the tracking helpers. |
| 1dae639e | tracks CSV counts a detection embedding | **C** (exports/tracks.py and its test) |
| a7770d59 | name the column "vector", record the job | **B** (c5988b55, 304eb51e). The exports test and tracking-test hunks go to **C**. |
| eab1e522 | test: read vectors as plain lists | **B** (ported to ami/ml/test_detection_embeddings.py) |
| 28ddd873 | vectors of any length, fill in existing detections | **B** (ml/0029, Algorithm.embedding_dimensions, feature-only path, NATS attach, schemas) |
| 069aa0d6 | default feature extractor per session | **C**: EventViewSet.feature_extractors, SessionFeatureExtractorSerializer, evaluate_tracking, tracking_form, admin_forms, tracking_task, `default_feature_algorithm_id` and `feature_extractors_with_vectors` (re-add them on top of B's `detections_covered` and `algorithm_ids_with_vectors`), TestDefaultFeatureExtractor and TestSessionFeatureExtractorsEndpoint. The feature-only tests in that commit's test_feature_extraction.py are in **B**. |
| 5f1eba0c | docs: embeddings reference | **B** (39e38b8f, tracking sections removed). C adds a tracking section. |
| 267d29c1 | docs: index entry | **B** |
| bb1369bf | default to the extractor covering most detections | **C** (choice logic and tests; B keeps only `detections_covered`) |
| a742932b | Collect heartbeat during feature-only filtering | **B** |
| 73d09b98 | never queue a feature-only task without boxes | **B** |
| 4ee569fd | docs: coverage default, repair migration, queue rules | Queue rules in **B**. Coverage default to **C**. The `main/0104` repair migration it describes is **obsolete** (replay rebuild). |
| a0996a82 | feature-only when a detector is listed too | **B** |
| dec57ce6 | classifier pipeline that also embeds does not reprocess | **B** |
| a6e5db83 | test: vectors of any length in the schema | **B** |
| 5da2ee6a | feature-only only when every other algorithm is a detector | **B** |
| b95f8299 | read vectors only from "features" | **B** |
| 88bee15e | fail a job whose boxes match no detection | **B** |
| 60319720 | fail a batch that stores nothing, count detections left without | **B** |
| f0f38cb8 | test: move a misplaced test, delete the old 0102 file | **Obsolete** (cherry-pick repair). FeatureVectorPresenceTestCase tests `features_2048` presence, so it goes with **C** only if C keeps that column. |
| 0cfd20e6 | half precision, key, project, job | **B** (model, `store()`, readers) and **A** (`project_scope.py`, ProjectScopedQuerySet, AlgorithmOutput, Classification.job and Detection.job). Dropped by design: Classification.features_2048 reads, `with_has_features`, `with_detections_with_features`, `with_frames_with_vectors`, `has_vector`'s classification branch and the UNION ALL reader fallback; **C** re-adds them only if it keeps `features_2048`. |
| 88d22ac0 | job on post-processing classifications; keep jobs that stored vectors | **A** (class masking and size filter set `job`; JobViewSet.perform_destroy) and **B** (`detectionembeddings` in `Job.has_stored_outputs`). The tracking_task.py hunk (job on the tracking determination) goes to **C**. |
| fe38d9c8 | docs: half precision, project, job | **B** |
| 2ec860ac | count only backbone vectors | **B** (`has_vector(key=…)`). The exports/tracks.py and `has_features` hunks go to **C**. |
| 98fdc182 | keep a station's jobs when it is deleted | **A** (in `jobs/0024_job_hidden_and_deployment_set_null` and test_job_outputs.py) |
| 01864b62 | docs: why a station's jobs outlive it | **A/B** (covered by the code comment in A and the B doc) |

## Commit map: `feat/algorithm-results-and-reviews` (over #1432 @d098429d)

| Commit | Subject (short) | Now |
|---|---|---|
| 9628ffa2 | results and reviews tables | **A** (0d3641bf). Kept in **C**: `AlgorithmResult.Kind.TRACKING`, `TrackingResultData`, `GroupingReviewPayload`, `Aspect.GROUPING` (A removed it in 31ae6283), and their registration in `ALGORITHM_RESULT_DATA_SCHEMAS["tracking"]` and `VALIDATION_REVIEW_PAYLOAD_SCHEMAS["grouping"]`. |
| c5109817 | hide a job whose outputs refer to it | **A** (84aa6d47). Its `jobs/0024_job_hidden` migration is obsolete. |
| e3bfd769 | grouping confirmations as reviews; history | Split. **A** (534c68d7): history endpoint, `add_comment`, `review_entry`, `TimelineEntry`, `occurrence_timeline`, serializers. **C**: the grouping writers and tracks.py hunks listed under "Grouping review writers", `OccurrenceSerializer.grouping_edited_since_verified`, the permission additions, the regroup-split review test, TrackChainAfterEdit query count 34 → 38. |
| 131b5ea2 | record what tracking, class masking, size filter changed | **A** (c31b1244) for class masking and the size filter. **C**: tracking_task.py hunks. |
| 8d0b87fb | UI: one occurrence timeline | **A** (6deea96b): hook, history model and test, AlgorithmResult card (without the tracking subtype), history stats, timeline, getUserLabel and its test, strings. **D**: track-review.tsx, grouping-confirmation.tsx, grouping-actions.tsx, capture.ts, occurrence-toolbar.tsx, `groupingEditedSinceVerified`, `onConfirmed` plumbing, TRACK_EDITED_SINCE_COMPLETE. Not in A and free for **D** (or a later A follow-up): adopting getUserLabel in occurrence-details.ts, occurrence.ts, human-identification.tsx and summary.tsx. |
| 788d5a64 | UI: grouping reviews and comments | **A** for comment-review.tsx. **D**: track-review, the `grouping` subtype entry and card, HISTORY_TRACK_COMPLETE_BY, HISTORY_SPLIT_FROM, HISTORY_TIME_SPAN, HISTORY_REVIEW_CHANGES. |
| 18c3d29e | docs: results, reviews, history endpoint | **Not ported yet.** The general half (tables, writers, endpoint) fits A as a follow-up doc; the grouping half goes to **C**. |
| e834dd38 | tracking result only on surviving keepers | **C** |
| 35d94af3 | one tracking result per occurrence across chains | **C** |
| fd37ceed | an edit stops a grouping confirmation standing | **C** (tracks.py, history.py, serializer, test hunks, and the one-line ValidationReview docstring addition: "an edit to the target also retires a grouping review") |
| 633ea746, 32dcbd71, bcbc4233 | merges of the embeddings branch | **Obsolete**. Their conflict resolutions only touch tests and docs already ported to A and B. |

## Grouping review writers C must carry

These lived in `ami/main/models_future/history.py` and `tracks.py` on the source branch. A keeps
only `add_comment`, `review_entry`, `TimelineEntry` and `occurrence_timeline` in history.py.

1. `verify_grouping(occurrence, user, timestamp=None)`, still `@transaction.atomic` and still
   calling `_lock_for_edit(occurrence)` first. It sets `grouping_verified_at = timestamp or
   timezone.now()` and `grouping_verified_by`, then calls `record_track_complete_review`.
   `timestamp` is only for replaying a confirmation made elsewhere.
2. `record_track_complete_review(occurrence, user, timestamp)` writes
   `ValidationReview(aspect="grouping", verdict="confirmed")` with a `GroupingReviewPayload`
   holding the detection ids at review time, the detections added and removed since the
   latest review, and the capture time span; `reviewed_result` is the occurrence's latest
   tracking result. When the person's current, not withdrawn review already names the same
   detections, it writes nothing. Otherwise it retires the person's earlier current grouping
   review (`is_current=False`) before inserting, so the partial unique index (one current
   review per target, aspect and user) holds.
3. `unverify_grouping` (atomic, `_lock_for_edit`) clears the two fields and calls
   `withdraw_track_complete_reviews`, which sets `withdrawn=True` on the current grouping
   reviews. It does not delete them.
4. Edits retire: `clear_grouping_verification` calls `retire_grouping_reviews(pks)`, which
   sets `is_current=False` on those occurrences' grouping reviews, so the cached fields and the
   reviews agree. `edited_since_track_complete_review` and `latest_track_complete_review` feed
   `OccurrenceSerializer.grouping_edited_since_verified`.
5. Split: `carry_confirmation_over_split(occurrence, pieces)` restates the confirmation as one
   review per piece, of that piece's own detections, with `split_from_occurrence_id` in the payload.
6. Merge: `move_history(source_pks, target)` moves results and reviews onto the keeper before
   the sources are deleted, by queryset update. Moved results and reviews stop being current
   (comments keep their state), so they stay in the keeper's history without standing for it.
   This is required: results and reviews cascade with their occurrence, so deleting a source
   first would lose them.

## Conflicts to expect in C, from A and B

- `ami/main/api/views.py`: A adds `HISTORY_ACTIONS = ("history", "reviews")`, a
  `get_permissions` override for `reviews` and an early return in `get_queryset` for history
  actions. #1272 has `SINGLE_OCCURRENCE_ACTIONS` and `UNFILTERED_ACTIONS`. Merge by hand.
- `Occurrence.check_custom_permission`: A allows `reviews` for `CREATE_IDENTIFICATION` only;
  #1272 also allows `DELETE_OCCURRENCES` and grouping verification. Keep both.
- `ami/ml/models/pipeline.py`: B adds `create_detection_embeddings` between detections and
  classifications; #1272 adds `features_2048` hunks in `create_classification`. B's
  `process_images` uses `pipeline_config.get(...)` (plain dict, as on main); #1272's typed
  `PipelineRequestConfigParameters` (e4a1702b) uses attributes. #1272's f4ad80e8 drop-and-warn
  for `ClassificationResponse.features` has nothing to apply to, because B's schema has no
  such field.
- `ami/jobs/models.py`: `MLJob.run` calls `job.scoped_source_images()` and
  `job.reprocesses_all_images()`; `process_images` has a feature-only branch.
- `ami/ml/post_processing/registry.py`: B registers `AddFeatureVectorsTask`; C adds the
  tracking task. `ami/main/admin.py`: B adds `run_add_feature_vectors` on three admins.
- `JobViewSet.perform_destroy` in A answers 409 for an unexpected `RestrictedError`; the source
  branch hid the job silently.
- Tracking reads vectors through `ami.main.models_future.embeddings.vectors_for_detections(ids,
  algorithm_id, key="embedding")`, which returns float32 numpy arrays, so cosine code must
  accept arrays.

## Review fixes made on A and B today

| Commit | Branch | Fix |
|---|---|---|
| 31ae6283 | A | `grouping` removed from `ValidationReview.Aspect` and from `main/0096` (C adds it back). |
| 506659b4 | A | A post-processing job's validated config is stored through `config.json()`, so a non-JSON value cannot fail the job save. |
| aadc2dbc | A | The history endpoint defers the `scores` and `logits` arrays when it reads predictions. |
| d824849d | B | A session or project scope for "Add feature vectors" now includes captures whose own project is empty but whose station is in the project. Adds an end-to-end test: task → ML job → real request building and `save_results`, with only the HTTP call stubbed. |

## Open items, not blocking the rebase

- Production deploy of `main/0096`: it adds an indexed `job_id` to `main_classification` and
  `main_detection`. The index is built without `CONCURRENTLY`, so writes to those tables wait
  while it builds. A partial index (`WHERE job_id IS NOT NULL`) built concurrently in a
  separate non-atomic migration would avoid that; not measured.
- The occurrence history has no UI to write a comment yet; the endpoint exists and is tested.
- An "Add feature vectors" run records no `AlgorithmResult`; the run is on the ML job's results
  stage and on each `DetectionEmbedding.job`.
- `Job.algorithms` (design 5.1) and `Algorithm.feature_extractor` (design 5.3) are not built.
