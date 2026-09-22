# Evaluating occurrence tracking against confirmed tracks

A first, read-only method for measuring how well tracking rebuilds tracks that people have
checked by hand. Companion to `reference/occurrence-tracking.md`.

## What counts as ground truth

An occurrence whose grouping a person confirmed (`Occurrence.grouping_verified_at` is set) is
taken to be one complete and accurate track: every detection in it is the same insect, and no
detection of that insect is missing from it.

Nothing is known about detections outside confirmed tracks. A predicted link from a confirmed
detection to an unconfirmed one might be right or wrong. So every number below is computed only
over **D, the set of detections that belong to a confirmed track**. Predicted tracks are cut
down to their detections in D before scoring.

## What is measured

All in `ami/ml/post_processing/tracking_evaluation.py::evaluate_tracks`, which returns a
`TrackingEvaluation` dataclass (`to_dict()`, `summary_lines()`).

| Field | Meaning | Read it as |
|---|---|---|
| `pairwise_precision` / `_recall` / `_f1` | Over every unordered pair of detections in D: predicted same-track pairs that are truly the same insect / all predicted same-track pairs; and / all true same-track pairs. | Precision drops with wrong merges; recall drops with fragmentation. Long tracks weigh more (pairs grow with length squared). |
| `link_precision` / `_recall` / `_f1` | A link is two detections that follow each other in time within one track. A predicted link is correct when the same two detections are adjacent in the confirmed track. | Closer to what an editor fixes by hand: one wrong link is one split or merge to undo. |
| `ground_truth_track_scores[]` | Per confirmed track: `length`, `fragments` (how many predicted tracks it is split across), `completeness` (largest piece / length), `exactly_recovered`. | `fragments == 1` and `exactly_recovered` means nothing to fix. |
| `predicted_track_scores[]` | Per predicted track touching D: `length` in D, `ground_truth_tracks` it spans, `purity` (largest share / length). | `ground_truth_tracks > 1` is a merge of different insects. |
| `merges`, `fragmented_tracks`, `exactly_recovered` | Counts of the above. | Headline counts for a table. |
| `mean_completeness`, `mean_purity` | Unweighted means over tracks. | Each track counts once regardless of length. |
| `ground_truth_tracks`, `detections`, `ground_truth_singletons`, `predicted_tracks`, `predicted_singletons` | Sizes. | Always report next to the scores: small benchmarks move a lot. |

Precision values are `None` (`null`, printed `n/a`) when nothing was predicted, for example when
no link passed the threshold. A confirmed single-detection track is a legitimate test case: a run
that attaches something to it loses pairwise precision and purity.

Link order within a track is capture time, then detection id to break ties.

## How to run it

### 1. Inside Antenna, re-linking the raw detections (management command)

```bash
docker compose run --rm django python manage.py evaluate_tracking --project <id> \
    [--event <id> --event <id>] [--cost-threshold 0.2] [--require-features | --no-require-features] \
    [--feature-extraction-algorithm <id>] [--format text|json] [--per-track]
```

- Ground truth: confirmed occurrences in the project (optionally only the listed sessions).
- Predictions: for each session holding a confirmed track, the tracking link step is re-run over
  every valid detection in the session as if none were linked (`propose_event_links` in
  `ami/ml/post_processing/tracking_task.py`). The stored `next_detection` links and occurrence
  assignment are ignored, because confirmed sessions have already been tracked and hand-corrected.
- Sessions where tracking would not run (no embeddings with `--require-features`, several feature
  extractors and none chosen) are listed under `skipped_events` and left out of the overall score.
- The task's other guards (fresh-session check, skip when people identified occurrences, fully
  processed) are not applied: they decide whether to write, not how to link.
- Nothing is written. The command runs in `transaction.atomic()` with `set_rollback(True)`, and
  `TestEvaluateTrackingCommand` checks detection and occurrence rows are identical afterwards.

Output: per-session scores and an overall score pooled over all scored sessions. JSON has the
keys `project_id`, `config`, `events[]` (`event_id`, `feature_extraction_algorithm_id`, `note`,
`links_proposed`, `evaluation`), `skipped_events[]`, `overall`.

### 2. Outside Antenna, from exported CSVs

```bash
python -m ami.ml.post_processing.tracking_evaluation --ground-truth gt.csv --predictions pred.csv \
    [--format text|json] [--per-track]
```

Standard library only; run from a checkout root (the package `__init__` imports nothing, so
Django does not need to be installed or configured). Both files use the tracks export format (one
row per detection; columns include `occurrence_id`, `detection_id`, `timestamp`, `frame_index`,
`grouping_verified`). Ground truth is the rows of the first file with `grouping_verified` true,
grouped by `occurrence_id`; predictions are all rows of the second file, grouped the same way. This
is the path for comparing a tracker that runs elsewhere: write its output in the same format.

### 3. From Python

```python
from ami.ml.post_processing.tracking_evaluation import evaluate_tracks, tracks_from_links

predictions = tracks_from_links(all_detection_ids, [(earlier_id, later_id), ...])
result = evaluate_tracks(ground_truth={det_id: track_id}, predictions=predictions,
                         timestamps={det_id: capture_time})
print("\n".join(result.summary_lines()))
```

## Known limits

- **Only confirmed tracks count.** Links into unconfirmed detections are neither rewarded nor
  penalised, so a tracker that wrongly attaches unreviewed detections to a confirmed track is not
  caught unless those detections are in another confirmed track.
- **Confirmed tracks are probably biased toward easy ones.** People are likely to confirm short,
  clean tracks first and leave crowded sessions for later. Not measured; worth checking how the
  confirmed set compares with the rest of each session (length, crowding) before reading scores as
  representative.
- **Timestamp ties.** Detections in one capture share a timestamp; the tie-break is detection id.
  A confirmed track should never hold two detections from one capture, so ties inside a track
  point to a data problem rather than an ordering question.
- **Sessions are scored whole.** The command re-links every detection in a session, including
  unconfirmed ones, because they compete for links with the confirmed ones.
- **No weighting by session.** The overall score pools detections, so one large session dominates.
  Per-session scores are in the output for that reason.

## Next steps (not built)

- Parameter sweeps: run the command over a grid of `--cost-threshold` values, with and without
  features, and table link F1 against threshold. A small wrapper script is enough to start.
- Per-species breakdown: group the per-track scores by the confirmed occurrence's determination.
  Untested idea; needs the determination added to the command's output.
- A dry-run tracking job (#1416) that stores proposed links for review in the UI would reuse
  `propose_event_links` rather than a second copy of the linking logic.
- Scoring the tracker's current stored output (rather than a fresh re-link) is a different
  question, answered by exporting the tracks CSV before and after hand-correction and comparing
  them with the CSV mode.

## Code map

- `ami/ml/post_processing/tracking_evaluation.py`: `evaluate_tracks`, `tracks_from_links`,
  `evaluate_csv_files`, `main`; no Django imports.
- `ami/ml/post_processing/tracking_task.py`: `iter_transition_links` (read-only, shared by the task
  and the evaluator), `propose_event_links`, `select_transition_links`, `save_links`.
- `ami/main/management/commands/evaluate_tracking.py`: the command.
- Tests: `ami/ml/post_processing/tests/test_tracking_evaluation.py` (metrics on hand-built cases,
  CSV adapter, command on a synthetic session, and proposed links equal to the links a run saves).
