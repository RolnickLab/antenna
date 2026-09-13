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
| A | Rank merge candidates by time adjacency, show the frames next to a track first, and merge several at once (#1414) | 4, 1, 2, 5, 22, 23 | S–M | – | `models_future/merge_candidates.py`, `OccurrenceViewSet.merge_candidates`/`merge`, merge dialog FE, `useTrackCandidates.ts` (move dialog uses an unranked hook) |
| B | Make reviewing a track faster: close on confirm, crop grid, names per frame, edited vs verified state (#1415) | 11, 8, 3, 6 | S–M | – | occurrence detail FE, `track_stats.grouping_summary`, model field `grouping_edited_at/by` + migration |
| C | Extend a track by clicking detections in the session view (#1418) | 7, 13 | M | A (comparison crop component) | session detail FE (`extend=` URL param), `POST /occurrences/{id}/add-detections/` (exists) |
| D | Preview a tracking run without writing (dry run) (#1416) | 14 | S | – | `tracking_task.py` (per-event atomic block already exists), job params |
| E | Bridge one-frame gaps, weight the cost terms, and use label agreement when linking | 9, 10, 12, 22 | M | D (measure before/after) | `tracking_task.pair_detections`, store per-link cost/similarity on `Detection` |
| F | Tracking playground: tune parameters live on a dozen captures | 21 | BE S–M, FE M | E (shared cost function) | new endpoint returning per-pair cost components; new page |
| G | Feature vectors for every detection, not only moths (#1417 + RolnickLab/ami-data-companion#170) | 4b, 18 | M (embedding output in the service schema + `DetectionEmbedding` table; the cheap "reuse the species classifier" path is ruled out, see measurements) | – | ami-data-companion pipeline, `ami/ml/schemas.py`, new model |
| H | Restrict a project's species to a regional list | 19 | S (deploy) | class masking PR #999 | deploy + TaxaList CSV import |
| I | Re-tracking a session after hand edits | fresh-guard finding | M | – | `event_is_fresh`, chain walk must respect `grouping_verified_at` |
| J | Max M per species per session (max in one frame vs individuals per night) | 15 | S–M | – | session stats annotation + export column |

Ticketed on 2026-09-13 as sub-issues of #1412 (A, B, C, D, G, and the processing-service counterpart of G). The data
checklist (keep the reviewed project unchanged, copy and reprocess with vectors for every detection, ask for regional
species checklists) is a comment on #1412. E, F, H, I and J stay in this plan until the annotation set exists.

Parked: movement prior per species (16), detector issues (17) belong to the processing service.

## Findings from the screenshots (added 2026-09-13, after reading all 33 images)

- The candidate picker shows the API order (tracker cost ascending). In one review case a 14-frame track of the same
  species, 3 % of the diagonal away and 99 % similar, ranked last of six: a small displacement zeroes the IoU term,
  which alone outweighs the appearance term. Package E should weight the terms; package A can default-sort by
  similarity when it is present.
- The "Move to another occurrence" dialog lists species and frame count only. It reads nearby occurrences through an
  unranked hook rather than the ranked endpoint, so it needs a `detection=` variant of that endpoint.
- Every frame the reviewer could not attach carried the moth/non-moth filter's "not a moth" label and no embedding
  (similarity shown as n/a). Package A removes the filter block; package G gives those frames a vector.
- The occurrence list shows no capture id or time, so a reviewer cannot tell from the list whether five single-frame
  occurrences of a distinctive species are consecutive captures (package C, list part).

## Measurements on the dev deployment (2026-09-13)

- **Why reviewers saw one or two usable candidates.** With the default ±5 minute window, a track in the dense
  session has 1,600–1,800 candidate occurrences and the endpoint returns the 50 lowest-cost. Those are almost all
  *overlapping* occurrences (other moths present at the same time, nearest-frame cost ≈1.1). The frame that actually
  continues the track ranked 4th, 35th, or not at all in the three dense tracks probed; in the quiet session (22–46
  candidates) everything fits and the true neighbour ranks first or second. Vector-less frames are not excluded:
  12–16 of ~500 made the top 50 in the dense session, all of them in the quiet one. Project default filters played
  no part: the dev project has threshold 0 and no taxa filters.
- **Vector-less detections are all the moth/non-moth filter's rejects:** 2,314 of 8,259 (dense), 264 of 782
  (quiet), 627 of 3,127 (mixed). The quiet session's occurrences are 131 of 154 "not a moth" singletons, the mixed
  one 485 of 1,855, so a fully annotated set has to bulk-handle those.
- **The dev project is now an annotation set** (127 identifications and 17 verified groupings by the partner since
  the demo) and must be frozen: no re-tracking in place; algorithm changes run on a copy or as a dry run (package D).
- **The cheap path to vectors is ruled out.** Running the species classifier on the rejected crops would add species
  classifications and change those occurrences' determinations inside the annotated set, and the binary gate has no
  backbone hook in the processing service. Package G therefore needs an embedding output in the service schema and a
  `DetectionEmbedding` table that never touches determinations.

## Order for the first dev session

1. **A** first: rank before/after candidates ahead of overlapping ones (or hide overlapping behind a toggle), default
   to the adjacent captures and let the window grow, apply the cap after that split, multi-select merge, comparison
   hover, Name/Frames sort. Unblocks three of the seven tests. (Default project filters were the first suspect; the
   dev project has none, see measurements.)
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
