# Occurrence tracking

How Antenna groups repeated detections of the same insect into one occurrence, what
the implementation actually does, and the traps that are invisible in a diff.

Feature branch: `claude/revive-tracking-feature-OyMO3` (PR #1272). Original work by
@mohamedelabbas1996 in #863.

## Vocabulary

Say **occurrence**, not "track". Tracking does not introduce a data model — `Occurrence`
has always held many `Detection` rows. Tracking is a *method of populating* that
relationship, using feature vectors and a per-detection link to the next frame. A
"track" in conversation means "an occurrence whose detections span several captures".

## Why it exists

Each detection gets its own occurrence when a pipeline runs, so an insect that sits
still for 37 captures contributes 37 to the abundance count for its species that night.
Tracking folds those back into one occurrence with a duration. The stated project
preference is that **more splits are better than incorrect lumping** — leaving one
animal as two occurrences costs a little accuracy, whereas merging two animals destroys
a record nothing downstream recovers. Set thresholds to err low.

## Data model

| Field | Where | Purpose |
|---|---|---|
| `Detection.next_detection` | `ami/main/models.py` | `OneToOneField("self", related_name="previous_detection", null=True)`. The chain link. UNIQUE, so two detections can never claim the same successor. |
| `Classification.features_2048` | `ami/main/models.py` | `pgvector.django.VectorField(dimensions=2048, null=True)`. The classifier's penultimate-layer embedding. |
| `Occurrence.detections` | reverse FK | Already existed. Tracking populates it; nothing about it is new. |

Migrations `0096_add_pgvector_extension`, `0097_classification_features_2048`,
`0098_detection_next_detection`.

The embedding is produced by the **classification model**, not a dedicated similarity
model — whatever classifier ran is the vector producer. A model trained for similarity
would be a better instrument, especially for re-identifying an individual across a
ten-minute sampling gap rather than across seconds of motion; nothing in the design
blocks swapping it, because the cost function only requires that one model produced all
the vectors being compared.

## How matching works

`ami/ml/post_processing/tracking_task.py`

Cost between two detections in consecutive captures, each term roughly 0 for a perfect
match and 1 for an unrelated pair:

```
(1 - cosine(f1, f2)) + (1 - IoU) + (1 - box area ratio) + (centre distance / diagonal)
```

Candidate pairs below `cost_threshold` are sorted and claimed greedily, each detection
at most once. Ties break on `(cost, det.pk, nxt.pk)` so re-runs are deterministic.
`assign_occurrences_from_detection_chains()` then walks `next_detection` chains and
folds each into the chain's **first existing occurrence** (merge-into-first), deleting
now-empty siblings.

`TrackingConfig` (the pydantic `config_schema`) knobs:

| Key | Default | Meaning |
|---|---|---|
| `source_image_collection_id` / `event_ids` | — | Scope. Exactly one is required. |
| `cost_threshold` | 0.2 | Link below this. See "choosing it" below. |
| `require_features` | True | False drops the appearance term and matches on geometry alone. |
| `require_fresh_event` | True | Skip sessions whose occurrences already span >1 detection. |
| `skip_if_human_identifications` | True | Protect reviewed sessions. |
| `feature_extraction_algorithm_id` | None | Disambiguate when several classifiers ran. |
| `require_completely_processed_session` | False | Off deliberately; see below. |

## The trap that matters most

**Tracking can only link detections in captures that are consecutive AND both
processed.** Detection volume is irrelevant. Most ML runs are deliberately samples
(ten-minute snapshots, every Nth frame), which leaves processed captures scattered and
nothing adjacent to link.

Run this before picking data or diagnosing an empty result:

```python
imgs = list(Event.objects.get(pk=E).captures.order_by("timestamp").values_list("id", flat=True))
with_dets = set(Detection.objects.filter(source_image__event_id=E)
                .values_list("source_image_id", flat=True).distinct())
adjacent = sum(1 for i in range(len(imgs)-1) if imgs[i] in with_dets and imgs[i+1] in with_dets)
```

Measured: one session with 4,138 captures and 14,366 detections had 663 processed
captures, none adjacent — zero linkable pairs. Another with 453 captures and 4,298
detections had 272 adjacent pairs and tracked well. Capture *cadence* is not a proxy;
a 4-second-interval session that was only sampled has almost nothing to link.

`Event.detections_count` / `occurrences_count` are cached and go stale — count from
`Detection.objects.filter(source_image__event_id=...)` when choosing data.

This is also why `require_completely_processed_session` defaults off: "the whole session
has been processed" is a state most real sessions never reach.

## Defect: the sequence is built from all captures, not processed ones

`tracking_task.py:358` is `source_images = list(event.captures.order_by("timestamp"))` —
every capture — and the loop pairs `source_images[i]` with `[i+1]`. On a sampled session a
processed capture's neighbours are unprocessed and hold no detections, so two processed
captures with unprocessed ones between them are **never compared to each other**, at any
threshold or time bound.

Measured 2026-09-02 (transitions with detections on both sides):

| event | captures | processed | evaluated | usable now | usable if fixed | median gap |
|---|---|---|---|---|---|---|
| 2610 | 4,138 | 663 | 4,137 | **0** | 662 | 60 s |
| 349 | 17,555 | 23 | 17,554 | **0** | 22 | 1,200 s |
| 6834 | 2,545 | 391 | 2,544 | 69 | 390 | 50 s |
| 6719 | 453 | 294 | 452 | 272 | 293 | 60 s |

Event 6719 is 65% processed and densely contiguous, so it barely shows the defect — which
is why every demo number came from it. Do not generalise from that session.

The fix is to build the sequence from processed captures only (a capture counts as
processed when any `Detection` row references it, sentinel included — the same signal
`filter_processed_images` uses). **Do not ship it alone.** Once pairs form between
processed captures the interval between them is unbounded, and `total_cost` has no elapsed-time
term, so a different insect settling in the same spot a night later scores like a
stationary one. Pair the fix with a configurable maximum gap; the minimum is bounded by
the data model, which has no sub-second timestamps.

## Choosing `cost_threshold`

Measure, do not guess. Best-match cost is bimodal. Geometry-only over one real session:
p5 0.037, p25 0.273, median 1.170, p75 1.356 — true matches near zero, unrelated pairs
near the sum of their terms, and a wide sparse valley between. Anywhere from ~0.4 to 1.0
gives nearly the same links. **0.4 is a good default for geometry-only on dense
captures.** Sampling the distribution is a short read-only script over `iou`,
`box_ratio` and `distance_ratio` from `tracking_task.py`.

## Running it

Django admin → **Capture sets** or **Events** → select rows → *Run Occurrence Tracking*.
An intermediate confirmation page renders the knobs; config is validated against
`TrackingConfig` at submit, not later in the worker. One job per capture set; an Events
selection is partitioned into one job per project. Stage metrics report events tracked /
skipped, links created, occurrences merged, and every skip is logged with its reason.

Built with `make_post_processing_action` (`ami/ml/post_processing/admin/actions.py`),
the same factory as Small Size Filter and Class Masking. Form in
`ami/ml/post_processing/admin/tracking_form.py`; the Events job builder in
`admin/tracking_actions.py`.

## Getting a session to try it on

`python manage.py create_demo_project` adds one night built for tracking: 24 captures two
minutes apart in an event of their own, ten simulated insects (six staying for a run of
six or more frames, four appearing once), 99 detections each on its own occurrence, and a
2048-d embedding per classification under algorithm `demo-tracking-classifier`. It needs
no processing service. The command prints which detections belong to which simulated
insect, and `--ground-truth-output PATH` writes that mapping as JSON so a run can be
scored against it — `score_tracking_run()` in `ami/tests/fixtures/tracking.py` does the
comparison.

Measured on the generated frames: an insect's own consecutive detections score under 0.15
geometry-only, unrelated pairs never below 1.2. Both a geometry-only run at
`cost_threshold=0.4` and a default run using the embeddings recover all ten groups
exactly. `--tracking-motion-scale` above its 0.2 default makes the session harder.
`--no-tracking-session` skips the extra night.

## Where results are visible

Nothing new was needed to *see* an occurrence's detections — the existing views were
always showing chains of length one.

- **Occurrence detail** — vertical list of detection thumbnails with timestamps and a
  *View in session* link each. Note the detail endpoint prefetches `-timestamp`
  (**newest first**, `prefetch_detections_for_detail()` in
  `ami/main/models_future/occurrence.py`), which is the reverse of chain order.
- **Session detail** — click an occurrence and it stays highlighted as you step through
  captures with the next/prev arrows.
- **Occurrences list** — `duration` stops being zero for merged occurrences; the
  snapshots column shows several crops. Sorting by duration descending is the fastest
  check that a pass produced anything sensible.

## Editing and confirming a grouping

`ami/main/models_future/tracks.py`, exposed as six actions on `OccurrenceViewSet`. All
operate on the occurrence's detections in timestamp order, so they behave sensibly on
occurrences that were never tracked.

| Endpoint (`POST /api/v2/occurrences/{id}/…`) | Body | Effect |
|---|---|---|
| `split-track/` | `{"detection_id": N}` | That detection and every **later** one move to a new occurrence |
| `remove-detection/` | `{"detection_id": N}` | One detection moves to an occurrence of its own |
| `merge/` | `{"occurrence_ids": [...]}` | Those occurrences are absorbed into this one and deleted |
| `add-detections/` | `{"detection_ids": [...]}` | Chosen detections move here from wherever they were |
| `verify-grouping/` | — | Records that a person confirmed this set of detections |
| `unverify-grouping/` | — | Clears that confirmation |

Adding a single frame is the one-detection case of merge, since a lone detection is
already an occurrence.

### Why verification is a separate axis

`Identification` records *what the animal is*. Nothing recorded *these detections are one
animal and none are missing*, so `Occurrence.grouping_verified_at` / `grouping_verified_by`
were added (migration `0099`). The two judgements are independent: a correctly grouped
occurrence can carry the wrong species, and vice versa. Confirmed groupings are the ground
truth that tracking changes get scored against — without them, evaluating a threshold
change is spot-checking.

### Two invariants every operation upholds

- **A chain link never crosses an occurrence boundary.** If a `next_detection` link
  survives across a human's split, the next tracking pass walks that chain and re-merges
  what they separated. `_cut_links_leaving()` cuts the links leaving any moved set.
- **Any edit that changes the detection set clears verification.** A person confirmed the
  set they were shown. `_clear_verification()` clears the **loaded instances as well as
  the rows** — clearing only via queryset `.update()` lets a later `occurrence.save()`
  write the stale confirmation straight back. That was a real test failure, not a
  hypothetical.

Ordering hazard inside `_absorb()`: identifications are reassigned *before* source
occurrences are deleted, because `Identification.occurrence` CASCADEs.

### Permissions

Restructuring (`split_track`, `remove_detection`, `merge`, `add_detections`) requires
`Project.Permissions.DELETE_OCCURRENCES`. Confirming (`verify_grouping`,
`unverify_grouping`) accepts **either** `CREATE_IDENTIFICATION` or `DELETE_OCCURRENCES` —
confirming is an expert judgement rather than a restructuring, but the roles that
restructure do not inherit identifying rights and must be able to confirm their own
corrections. `MLDataManager` holds `DELETE_OCCURRENCES` but not `CREATE_IDENTIFICATION`,
which is what forced the `or`.

## Gotchas

- **`OccurrenceViewSet` sets no `permission_classes`**, so it inherits the project-wide
  `IsActiveStaffOrReadOnly` default from `config/settings/base.py`. A new POST `@action`
  returns 403 for everyone non-staff and object permissions never run. Scope
  `get_permissions()` per action.
- **`check_custom_permission` derives the codename as `f"{action}_{model_name}"`**, so a
  `split_track` action looks for a `split_track_occurrence` permission that does not
  exist. Override on the model. There is **no `update_occurrence` permission**.
- **`OccurrenceQuerySet.valid()` excludes `determination__isnull=True`.** An occurrence
  created by a split is invisible to the API until it has a determination — real tracked
  data always has classifications, so this mostly bites test fixtures. Give fixture
  detections a classification and call `occurrence.save()`.
- **`Occurrence.save()` recomputes determination** via `update_occurrence_determination`.
  After moving detections between occurrences, save both.
- **`Identification.occurrence` CASCADEs.** Any merge that deletes an absorbed occurrence
  must reassign its identifications to the survivor first — `_absorb()` does. The batch
  tracking task sidesteps the question entirely by refusing already-grouped sessions.
- **pgvector must be in the Postgres image AND the Python environment of both the django
  and celeryworker images.** With `VectorField` on the model but the module missing from
  the worker, `bulk_create` can save the row and silently drop the vector.
- **Pull-mode workers get no config from Antenna.** `PipelineProcessingTask` has no
  config field, so a worker reads `AMI_INCLUDE_FEATURES` from its own environment.
  Setting `Pipeline.default_config` does not reach it.

## Open work

- **A front end for any of it.** The six editing endpoints exist and are tested; nothing
  in the interface calls them. Five directions are mocked up, the cheapest being a ghost
  trail of neighbouring frames drawn over the session capture, which reuses the overlay
  already at `ui/src/.../capture.tsx`.
- **Sequence defect + a maximum pair gap** — see the section above; these ship together.
- **A re-run must not overrule a confirmation.** Nothing currently stops a second tracking
  pass from re-merging a grouping a person split and confirmed. `event_is_fresh` refuses
  already-grouped sessions wholesale, which is a blunt substitute.
- **Idempotent incremental tracking** — see `docs/claude/planning/idempotent-incremental-tracking.md`.
  The unit of work becomes a pair of adjacent processed captures rather than a session,
  so a pass is always safe to re-run and picks up only new work.
- **A dedicated similarity model** rather than borrowing the classifier's embedding.
