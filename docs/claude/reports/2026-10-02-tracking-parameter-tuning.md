# Tracking parameter tuning and a by-eye audit of proposed tracks (2026-10-02)

This report summarises how the occurrence-tracking parameters were tuned on a partner's evaluation
project, and what a by-eye review of the resulting tracks found. It covers three cameras: a busy night
dominated by micromoths ("the busy micromoth night"), a medium night with larger moths ("the medium
macromoth night") and a quiet night with a few large moths ("the quiet night"). The partner confirmed tracks
in a one-hour window of each night; those windows are the benchmark.

Related code: #1442 (cost terms and the sweep harness), #1439 (detection embeddings, feature-only jobs,
occurrence history), #1444 (resetting a session's tracking). Reference docs: `reference/occurrence-tracking.md`,
`reference/tracking-evaluation.md`, `reference/detection-embeddings.md`.

**Tags.** [M] measured: a real tracking job, or the tracker's own code run read-only and scored against the
confirmed tracks, or a count made by eye. [S] simulated: the tracker's linking code run read-only without
ground truth; wherever a simulated setting was also run for real, the two matched detection for detection.
[E] estimated: a sample rate multiplied out, or a figure from reading code. Intervals are 95% Wilson
intervals. "Best case" counts tracks the reviewer marked `unsure` as correct, "worst case" counts them as joins.

## 1. Summary

**Recommended setting: D3.** Link consecutive detections on box overlap plus BioCLIP 2.5 appearance, with a
hard similarity floor, stricter matching in crowded captures and a penalty when the species classifier
confidently names two unrelated taxa (exact values in section 7).

Full nights, real runs [M]:

| night | detections = occurrences before | occurrences after D3 | fewer to review | unique determinations |
|---|---|---|---|---|
| busy micromoth night | 36,578 | 28,270 | **22.7%** | 873 → 822 |
| medium macromoth night | 13,094 | 7,084 | **45.9%** | 601 → 519 |
| quiet night | 4,983 | 340 | **93.2%** | 56 → 47 |

Joins of two different insects, by eye, two seeded samples combined [M]: long tracks (4+ captures) **0 / 75**
on the busy night and **0 / 75** on the medium night (upper bound 4.9% each), **0 / 25** on the quiet night
(every long track); short tracks (2–3 captures) **1 / 40** (0.4–12.9%), 0 / 39 and 0 / 16.

For comparison [M]: the old default (threshold 0.2) joined no insects in 120 sampled tracks but saves only
9–28% on busy and medium nights; threshold 1.0 on geometry saves 29% / 50% / 93% but joined insects in 6.3%
(worst case 15%) of long busy-night tracks; threshold 1.5 joined insects in 90% of long tracks on the busy
micromoth hour.

**Limits.** One reviewer, working from crops and capture views, cannot see two insects of the same species
swapping on one spot, so same-species joins are undercounted everywhere. Three cameras and three nights; the
benchmark hours are parts of the same nights.

**Decisions for the partner:** D3 versus D1 (slightly more saving, one definite join and several unsure tracks);
whether resting moths split by the species penalty are acceptable until a fix lands; who sets the staff-only
parameters; whether a specialist looks at four links that cannot be settled from the images.

## 2. Data

- **Benchmark hours** [M]: three one-hour windows of 180 captures at about 20 s intervals; 8,259 / 782 / 3,127
  detections (busy micromoth / quiet / medium macromoth). 49 partner-confirmed tracks, 40 of 2+ detections and
  9 singletons; 1,212 ground-truth links, 29 of them moves (boxes do not overlap).
- **Full nights** [M]: about 1,080 captures each; 36,578 / 13,094 / 4,983 detections. Only the benchmark hour
  had been processed originally; the rest was detected, classified and embedded for this study.
- **BioCLIP 2.5 vectors for every detection** (1,024-d), produced by feature-only ML jobs that send existing
  detections to the processing service.
- **Limits of the ground truth.** Confirmed tracks are clear, well-separated moths, so scores against them say
  little about crowded captures. With classifier-backbone vectors required, only 83.4% of ground-truth links
  have a vector at both ends, which caps recall at 0.834.

## 3. Method

**Cost.** For two detections in consecutive captures:
`(1 − cosine similarity) + (1 − IoU) + (1 − area ratio) + centre shift / diagonal`. Pairs below
`cost_threshold` are claimed greedily, cheapest first. Options added in #1442 (off by default, staff-only):
term weights, appearance calibration, an appearance gate, activity scaling of the distance term, a species
gate, stationary-first and a move rule.

**Structural fact.** `1 − IoU` is 1 for boxes that do not overlap and every other term is at least 0, so at a
threshold of 1.0 or less only overlapping boxes can link. Joins between confirmed tracks appear only above 1.0,
and moving moths are never linked at the recommended settings.

**Sweeps** (read-only, rolled back) [M]: about 2,500 settings over three rounds (classifier-backbone vectors, then
BioCLIP vs backbone with calibration, gates and a move rule), 47 s to 7.5 min per grid.

**Why confirmed-track metrics hide joins.** Precision and merges are scored only inside confirmed tracks. The
first sweep reported **0 merges** for threshold 1.5 with activity scaling; by eye, **90%** of its long tracks on
the busy micromoth hour joined different insects [M]. From then on every candidate was judged by eye.

**By-eye audit.** Three audits (464, 1,130 and 316 sampled tracks). Seeded samples of tracks not wholly inside a
confirmed track: 40 of 4+ captures and 20 of 2–3 per setting and night. The last two audits were blind to the
setting. Every frame shown up to 100 frames; longer tracks show every link overlapping below IoU 0.85 and every
10th frame. Ambiguous tracks got enlarged crops, the full capture with every detection drawn, a four-capture
view around a link, and database checks for a detection left behind at the old position. Verdicts: same, merge,
unsure, background. Re-judged sequences kept their verdict in 128 of 129 and 76 of 77 cases.

**Real runs against the simulation.** Five settings were run as real tracking jobs on the three full nights,
resetting between settings. In all 15 setting-night cells the real multi-detection occurrences equalled the
simulated tracks detection for detection [M], so audits of simulated and real tracks sample one population.

## 4. Settings

| setting | threshold | vectors | extra |
|---|---|---|---|
| A (default) | 0.2 | required | none |
| B | 1.0 | not required (classifier backbone where present) | none |
| C | 1.5 | not required (backbone) | activity scaling, log |
| D1 | 1.0 | BioCLIP | gate 0.47, activity scaling log (reference 5) |
| D2 | 1.0 | BioCLIP | D1 + species penalty 0.5 at score 0.2 |
| **D3** | **0.9** | BioCLIP | D2's options |

## 5. Results

**Benchmark hours against confirmed tracks** (12,168 detections) [M]:

| setting | link P | link R | exact multi-detection tracks (of 40) | occurrences after |
|---|---|---|---|---|
| A | 1.000 | 0.624 | 7 | 9,774 |
| B | 1.000 | 0.960 | 22 | 7,415 |
| C | 1.000 | 0.983 | 28 | 3,226 |
| D1 | 1.000 | 0.939 | 22 | 7,834 |
| D2 | 1.000 | 0.931 | 22 | 7,935 |
| **D3** | 1.000 | **0.917** | **20** | **8,064** |

**Full nights, occurrences after (saving)**:

| setting | busy micromoth night | medium macromoth night | quiet night | source |
|---|---|---|---|---|
| A (BioCLIP) | 33,365 (8.8%) | 10,232 (21.9%) | 818 (83.6%) | [M] |
| B (backbone) | 26,110 (28.6%) | 6,502 (50.3%) | 327 (93.4%) | [S] |
| C (backbone) | 10,172 (72.2%) | 3,822 (70.8%) | 275 (94.5%) | [S] |
| D1 | 27,573 (24.6%) | 6,847 (47.7%) | 329 (93.4%) | [M] |
| D2 | 27,861 (23.8%) | 6,924 (47.1%) | 330 (93.4%) | [M] |
| **D3** | **28,270 (22.7%)** | **7,084 (45.9%)** | **340 (93.2%)** | [M] |

D3 keeps 79% / 91% / 100% of B's saving. Most occurrences left on busy nights are single detections; tracking
shortens the list mainly by collapsing moths that sit still.

**Joins by eye, long tracks (4+ captures), best / worst case** [M]:

| setting | busy night | medium night | quiet night | hour windows |
|---|---|---|---|---|
| A | not audited | not audited | not audited | 0 / 120 |
| B | 5/80 = 6.3% / 12/80 = 15.0% | 1/40 / 2–3 of 40 | 0 / 19 | 4/122 / 6/122 |
| C | not audited | not audited | not audited | 94/123 = 76% |
| D1 | 0/80 / 3/80 = 3.8% | 1/76 = 1.3% | 0 / 19 | 0/81 / 2/81 |
| D2 | 0/40 / 0/40 | 0/40 / 0/40 | 0 / 20 | 1/81 / 2/81 |
| **D3** | **0/75 (0–4.9%)** | **0/75 (0–4.9%)** | **0 / 25** | 0/81 / 1/81 |

Short tracks (2–3 captures), D3: 1/40 on the busy night, 0/39 medium, 0/16 quiet [M]. Scaled to the busy night's
2,779 short tracks, that one join is about 70 joined short tracks, with a very wide interval [E].

Every definite join found is between visibly different insects, and almost all follow one pattern: one insect
leaves, a different one lands on the same spot within one capture interval, the boxes overlap, and the track
continues. D3 still makes two known wrong links (IoU 0.79 and 0.73): one "leaves and lands", one neighbour swap
where the first insect is still detected just beside the box.

**Run time** [M]: real tracking jobs 53 s to 7 m 41 s per night (D3 on the busy night 7 m 41 s); resetting three
nights 9–59 s.

## 6. Vectors: BioCLIP 2.5 against the classifier backbone [M]

| | classifier backbone | BioCLIP 2.5 |
|---|---|---|
| coverage (benchmark detections) | 74% | 100% |
| negative components | none (ReLU; 72% exactly zero) | about 50% |
| random pair similarity, median | 0.97 | 0.51 |
| same insect, median | 0.992 | 0.95 |
| different insect within 3 box sizes, median | 0.957 | 0.39 |
| AUC, same vs nearby different | 0.980 | 0.979 |

Both rank pairs equally well; only BioCLIP has a usable scale. The backbone is trained with a classification loss
behind a ReLU, so every crop shares one large direction and its appearance cost moves by about 0.05 between true
and false pairs, next to geometry terms of up to 3. BioCLIP is trained contrastively and spreads crops over the
sphere. The joins found by eye sit where geometry already costs about 0.7; a BioCLIP similarity of 0.41–0.67 pushes
them over the threshold. Switching setting B to BioCLIP vectors blocks 9 of 10 known join links, and activity
scaling blocks the tenth (fitted on those same links).

Calibration (a floor and ceiling on similarity) rescues the backbone but makes look-alike joins cheaper with
BioCLIP. The 0.47 gate is the 1st percentile of true BioCLIP pairs and costs about 0.006 recall. Centring the
backbone vectors (subtract the mean, renormalise) spreads random-pair similarity to −0.17–0.26; its effect on
tracking is untested. BioCLIP at threshold 0.2 looked worse than the backbone (link R 0.547 vs 0.624) only because
its wider scale taxes true pairs more at the same threshold.

## 7. What did not work [M]

- Threshold 0.2: recall 0.624, 7/40 tracks exact.
- Thresholds above 1.0 (setting C): the track hops to the nearest insect; 76% of long tracks joined.
- The "different-label link" proxy as a join detector: missed all 4 joins at B, caught 19 of 346 wrong links at C.
- Calibration with BioCLIP; gates above 0.6; species forbid at score 0.2 (loses 127 of 1,205 confirmed links);
  thresholds 1.1–1.2.
- The move rule (3–8 of 29 moving links, about one doubtful link per correct move) and stationary-first (no change
  without required features).
- A similarity floor below 0.80 for partial overlaps: blocks both remaining D3 joins but cuts 645 links on the
  busy and medium nights, and 30 of 30 sampled were the same insect.
- A static-object rule: the longest track (930 captures) is a real resting moth, and the only static non-insect
  objects found are 2-frame sheet folds.

## 8. Recommendation

```json
{
  "cost_threshold": 0.9,
  "require_features": false,
  "feature_extraction_algorithm_id": "<the BioCLIP 2.5 embedding algorithm>",
  "appearance_min_similarity": 0.47,
  "activity_scaling": "log",
  "activity_reference_count": 5,
  "species_gate": "penalty",
  "species_gate_penalty": 0.5,
  "species_gate_min_score": 0.2,
  "species_label_algorithm_id": "<the project's species classifier>"
}
```

Other fields at their defaults. Algorithm ids differ per deployment and must be looked up.

**Who can change what.** Project members who can run tracking may set the sessions, `cost_threshold`,
`require_features`, the feature extractor and `require_completely_processed_session`. Everything else in the block
above is staff-only. A member-started run therefore gets the defaults for those fields, not D3; running D3 needs a
superuser, stored per-project settings (not built), or opening some fields to members. Lowering the threshold is
safe for a member to try; raising it above 1.0 is what produced setting C.

**Follow-ups to discuss:** skip the species penalty when boxes overlap at IoU ≥ 0.9 (no known wrong link overlaps
above 0.79, and resting moths whose label flips would stay whole); a neighbour-swap tie-break in the assignment
(as a hard block it cuts 59 links over three nights, 1 of 20 sampled wrong).

## 9. Risks and open questions

- Same-species swaps on one spot are invisible in crops; every join rate undercounts them.
- The benchmark hours are parts of the full nights; three cameras in total.
- Samples are small: one join moves a night's rate by 2.5% (long) or 5% (short).
- Four links remain unsure after a second look (dark capture, frame edge, colour change in place).
- The species penalty split a resting moth of 930 captures into three occurrences at label flips between related
  species. How often this happens was not counted.
- Moving moths are not linked at thresholds ≤ 1.0.
- Resetting a session left tracking history from undone runs on occurrences; a fix is pending on #1444.
- The merge picker scores with default settings, not the settings the run used.

## 10. Production readiness

| item | state |
|---|---|
| pgvector on the production database | not checked; required by the embeddings table |
| BioCLIP on a processing service | draft PR in the processing-service repo; needs a GPU worker |
| Embedding existing detections | feature-only ML jobs (#1439); measured 32 detections/s on one RTX 3090 inside the service, about 3 s per capture end to end, dominated by image download [M]; roughly one hour per 1,000-capture night per worker [E] |
| Result backend | sync ML jobs can end FAILURE after saves succeed (#1443), and job creation can 500 on an idle broker (#1437); run ML jobs one at a time until both land |
| Staff-only fields through the API | refused for every user on the PR heads; a superuser exemption is pending |
| Algorithm ids | look up per deployment |

**Landing order:** #1435 (CI) → main into #1272 → #1432 → #1439 → #1442 → #1444; #1441 after #1432; #1437, #1438
and #1443 to main independently. Then deploy behind the per-project tracking flag.

## 11. Next steps

1. Agree the decisions in section 1 with the partner.
2. Land the pending fixes on their PR branches and the stack in the order above.
3. Check pgvector in production; deploy BioCLIP; embed existing detections.
4. Run D3 on the partner's nights; the partner reviews in the UI.
5. If wanted, build the species-gate overlap exemption and re-audit a sample.
6. Test D3 on a camera or night it was not tuned on.
