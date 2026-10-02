# Algorithm results and validation reviews

Reference for agents. Where a job's decision about an occurrence, capture or session is stored
(`AlgorithmResult`), where a person's verdict is stored (`ValidationReview`), and how the
occurrence history endpoint merges them. Design: the model outputs design note (#1453),
sections 5.4, 5.6 and 5.7.

## Tables (`ami/main/models.py`, migration `main/0103_algorithm_results_and_validation_reviews.py`)

- `AlgorithmResult(AlgorithmOutput)`: `project` NOT NULL, exactly one of `occurrence` /
  `source_image` / `event` (CHECK `algorithm_result_one_target`), `algorithm`, `job` (RESTRICT,
  nullable), `kind` (open vocabulary: `tracking`, `class_masking`, `size_filter`), `value`
  (float, for filtering and sorting), `data` (JSON, validated per kind by
  `ALGORITHM_RESULT_DATA_SCHEMAS` in `ami/main/schemas.py`; a kind with no schema can carry
  `value` only), `is_current`. At least one of `value`/`data` (CHECK). Partial unique
  `(target, algorithm, kind) WHERE is_current` per target; index `(occurrence, -timestamp)`;
  partial index `(project, kind, value) WHERE is_current AND value IS NOT NULL`.
- Write with `AlgorithmResult.objects.record(**fields)` or `record_many(rows)`: clears
  `is_current` on the target's previous row of the same algorithm and kind, then inserts.
  Rows are never rewritten otherwise.
- `ValidationReview`: `project` NOT NULL, exactly one of `occurrence` / `detection` /
  `source_image` / `event`, `user` (SET_NULL), `aspect` (`identification`, `grouping`, `bbox`,
  `count`, `person_present`, `night_valid`, `comment`), `verdict` (`confirmed` / `rejected` /
  `corrected`; null only and always for `comment`, which needs non-empty `comment` text),
  `identification` FK, `reviewed_result` FK to `AlgorithmResult`, `payload` (validated per aspect
  by `VALIDATION_REVIEW_PAYLOAD_SCHEMAS`), `comment`, `timestamp`, `withdrawn`, `is_current`.
  Partial unique `(target, aspect, user) WHERE is_current AND aspect <> 'comment'`.
  `ValidationReview.objects.current(aspect, verdict)` = `is_current AND NOT withdrawn`.
- Writers implemented: `grouping` (via `verify_grouping`) and `comment`. Identification rows do
  not write reviews yet.
- `project` on both tables is filled by `fill_project_ids` from whichever target is set
  (`project_parent_paths`, `ami/main/models_future/project_scope.py`): the target's project,
  else its deployment's, else `ProjectScopeError`; disagreement keeps the target's and logs a
  warning. `project_mismatch_counts()` covers both tables.

## Grouping reviews (`ami/main/models_future/history.py`, `tracks.py`)

- `verify_grouping(occurrence, user, timestamp=None)`: locks the session (5 s, `SessionBusy`
  -> 409), sets `grouping_verified_at = timestamp or now` and `_by`, then
  `record_track_complete_review`: writes a `grouping`/`confirmed` review with
  `payload.detection_ids`, `detections_added/removed` vs the occurrence's latest own review
  (`payload__occurrence_id`), and `reviewed_result` = the current tracking result. Skipped when
  the user's current, non-withdrawn review of this occurrence has the same detection ids, so a
  replay at the original time is idempotent.
- `unverify_grouping` clears the cache and sets `withdrawn` on the standing grouping reviews.
- A regroup split restates the review per piece (`carry_confirmation_over_split`).
- Merges (`_absorb`, tracking) call `move_history`: results and reviews move to the keeper with
  `is_current = False` (comments keep theirs).
- `OccurrenceSerializer.grouping_edited_since_verified` compares current detections with the
  latest own grouping review.

## Writers of `AlgorithmResult`

- Tracking: `TrackingResults` in `ami/ml/post_processing/tracking_task.py`, one per changed
  occurrence (settings, feature extractor, frames linked, merged ids, cost stats, taxon before
  and after).
- Class masking: `make_classifications_filtered_by_taxa_list`, one per re-scored occurrence.
- Size filter: `SmallSizeFilterTask.run`, one per occurrence with a flagged detection.

## Endpoints

- `GET /occurrences/{id}/history/` (`occurrence_timeline`): results, reviews, identifications
  and one prediction per algorithm, newest first; 9 queries regardless of entries (pinned by
  `HISTORY_QUERIES` in `ami/main/test_occurrence_history.py`). Reviews come as `type=review`,
  `subtype=<aspect>`.
- `POST /occurrences/{id}/reviews/` `{"comment": "..."}`: adds a comment; identifier rights
  (`CREATE_IDENTIFICATION` or `DELETE_OCCURRENCES`), no tracking flag needed.
- `DELETE /jobs/{id}/`: hides the job (`Job.hidden`) when `has_stored_outputs()`; the list
  leaves hidden jobs out unless `include_hidden=true`.

## UI

- `ui/src/data-services/models/occurrence-history.ts` (types, `getTimelineItems`),
  `ui/src/pages/occurrence-details/identification-card/` (`occurrence-timeline.tsx`,
  `track-review.tsx`, `comment-review.tsx`, `algorithm-result.tsx`). No comment form yet.
