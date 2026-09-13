# Occurrence tracking: work plan from the first partner review (2026-09-13)

Source: a partner reviewed the tracking branch (PR #1272 head 2560b4f9) on a dev deployment with three benchmark
sessions and wrote up seven hands-on tests, plus our own notes from the demo. Verbatim feedback and screenshots are in
the session notes under `docs/claude/sessions/` dated 2026-09-13 (kept out of the public repo).
Meta ticket: #1412. Numbers in brackets refer to the feedback table in the session doc.

Headline from the review: the tracker is conservative (1 wrong link in 77 hand-checked tracks of one species) and the
edit tools work, but reviewers cannot finish tracks because frames rejected by the moth/non-moth filter or hidden by
project filters never appear as merge candidates, and building a track by hand needs too many clicks.

## Work packages

| Pkg | Title (issue title, effect first) | Items | Effort | Depends on | Files |
|---|---|---|---|---|---|
| A | Offer every frame of the session as a merge candidate, and merge several at once | 4, 1, 2, 5 | S–M | – | `models_future/merge_candidates.py`, `OccurrenceViewSet.merge_candidates`/`merge`, merge dialog FE |
| B | Make reviewing a track faster: close on confirm, crop grid, names per frame, edited vs verified state | 11, 8, 3, 6 | S–M | – | occurrence detail FE, `track_stats.grouping_summary`, model field `grouping_edited_at/by` + migration |
| C | Extend a track by clicking detections in the session view | 7, 13 | M | A (comparison crop component) | session detail FE (`extend=` URL param), `POST /occurrences/{id}/add-detections/` (exists) |
| D | Preview a tracking run without writing (dry run) | 14 | S | – | `tracking_task.py` (per-event atomic block already exists), job params |
| E | Bridge one-frame gaps and use label agreement when linking | 9, 10, 12 | M | D (measure before/after) | `tracking_task.pair_detections`, store per-link cost/similarity on `Detection` |
| F | Tracking playground: tune parameters live on a dozen captures | 21 | BE S–M, FE M | E (shared cost function) | new endpoint returning per-pair cost components; new page |
| G | Feature vectors for every detection, not only moths | 4b, 18 | ADC S (reuse species classifier) / M (dedicated embedding model + `DetectionEmbedding` table) | – | ami-data-companion pipeline, `ami/ml/schemas.py`, new model |
| H | Restrict a project's species to a regional list | 19 | S (deploy) | class masking PR #999 | deploy + TaxaList CSV import |
| I | Re-tracking a session after hand edits | fresh-guard finding | M | – | `event_is_fresh`, chain walk must respect `grouping_verified_at` |
| J | Max M per species per session (max in one frame vs individuals per night) | 15 | S–M | – | session stats annotation + export column |

Parked: movement prior per species (16), detector issues (17) belong to the processing service.

## Order for the first dev session

1. **A** first: the candidate queryset must bypass project default filters (root cause confirmed at
   `OccurrenceViewSet.merge_candidates` → `self.get_queryset()` → `apply_default_filters`), flag hidden rows, add a
   nearest-frames mode, multi-select merge, comparison hover, Name/Frames sort. Unblocks three of the seven tests.
2. **B** quick parts: close-on-confirm + next (11), crop grid (8), per-taxon breakdown and detection id/score on the
   card (3). Edited-vs-verified state (6) needs a migration; do it if time allows.
3. **D** dry run: cheapest way to answer "what would threshold X do" on a whole session.
4. **C** click-to-extend, if A's crop comparison component exists by then.
5. **E/F** are algorithm work; benchmark before and after with the dry run from D.

Each package is its own branch off `integration/tracking-inrae` (or its successor after #1272 merges), PR into it,
tests + `tsc` + lint per the repo checklists.

## Definition of done per package

- A: a test with an occurrence excluded by taxa filters and one under the score threshold both appear as candidates
  and can be merged; picker renders a "hidden by project filters" badge; multi-select merges in one request.
- B: confirm dialog closes and focus moves to the next occurrence; crop grid shows all frames; card lists distinct
  taxa with counts.
- C: from the session view with `extend=<id>`, clicking a box adds it and advances; frames already in a multi-frame
  track prompt to merge the whole track.
- D: job with `dry_run=true` logs links/tracks/histogram and leaves the database unchanged (assert counts in a test).
- E: on the benchmark windows, gap-bridging does not add a single cross-species link in the hand-checked set.
