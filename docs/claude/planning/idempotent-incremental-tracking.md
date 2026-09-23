# Idempotent, incremental occurrence tracking

Status: design proposal, not implemented. Written 2026-09-02.

## The problem

Occurrence tracking today is a batch operation an operator runs over a whole session: it walks
every pair of consecutive captures, links detections that look like the same insect, and folds
each resulting chain into a single occurrence. Because re-running it over data that has already
been grouped can delete occurrences that carry human identifications, it is guarded by
`require_fresh_event`, which refuses any session where an occurrence already spans more than one
detection. That guard makes the operation single-shot: a session can be tracked once, and only
before anyone has touched it. It also leaves an unanswerable question at the centre of the design
— when is a session finished? — because most processing runs are deliberately samples, so "every
capture has been processed" is a state that frequently never arrives. This document proposes
replacing the batch pass with one that is always safe to run, any number of times, at any point:
the unit of work becomes a single pair of adjacent processed captures, running twice does nothing
the second time, and running after more captures arrive picks up only the new work.

## Evidence that reframes the problem

Three measurements against the local database (a copy of production) shaped the design more than
anything in the code. Session identifiers are omitted because this repository is public.

**Sampling is the norm, not the exception.** The session with the most processed captures in the
local database holds 4,497 captures, of which 750 have any detection at all — 17%. The session
with the most captures holds 23,362, of which 65 are processed — 0.3%. Across the ten
most-processed sessions the share never exceeds 17%. Measured. This is the empirical form of the
user's point: waiting for a session to be complete is waiting for something that does not happen.

**Adjacent processed captures are minutes apart, not seconds.** In these sessions the camera
captures every 10 seconds, but the processed subset is a uniform sample: the median gap between
one processed capture and the next is 60 seconds in five of the sessions measured, 45 seconds in
one, and 600 seconds in another. Measured. The current cost function assumes small motion between
frames, and this is discussed under "What I am unsure about" below, because it has consequences
well beyond this design.

**The current implementation is close to a no-op on sampled sessions.**
`assign_occurrences_by_tracking_images` builds its sequence from `event.captures.order_by("timestamp")`
— every capture, processed or not (`ami/ml/post_processing/tracking_task.py:358`). On a session
where 65 of 23,362 captures carry detections, almost every one of the 23,361 transitions it
evaluates is between two captures with no detections, and two processed captures are almost never
adjacent to each other, so almost no links can be created. This is a pre-existing defect rather
than something the redesign introduces, but the fix falls out of the redesign: adjacency has to be
defined over processed captures.

## The design

### The unit of work is a transition between two processed captures

Order a session's *processed* captures by timestamp. Each consecutive pair is a **transition**.
Evaluating a transition means running the existing greedy matcher over the detections of the two
captures and writing `Detection.next_detection` links for the matches it accepts. A capture counts
as processed when at least one `Detection` row references it, including a null-marker sentinel —
the same signal `filter_processed_images` already uses to decide an image needs no further work
(`ami/ml/models/pipeline.py:71`). A capture that was processed and genuinely contained nothing
therefore takes part in the sequence and, having no detections to match, ends the chains that
reach it. That is the behaviour the batch pass already has, and this design does not change it.

### The marker is a recorded successor on the capture

Each capture records the capture it was last evaluated *forward* against:

```python
# ami/main/models.py, on SourceImage
tracking_successor = models.ForeignKey("self", null=True, blank=True, db_index=False,
                                       on_delete=models.SET_NULL,
                                       related_name="tracking_predecessors")
tracking_evaluated_at = models.DateTimeField(null=True, blank=True)
```

A transition is **outstanding** when a capture's recorded successor is not the capture that
actually follows it in the processed sequence. Writing the rule out:

| Recorded successor | Actual successor | Outstanding? | Meaning |
|---|---|---|---|
| `NULL` | capture B | yes | never evaluated |
| capture B | capture B | no | already evaluated, nothing to do |
| capture B | capture C | yes | a capture arrived in between; the old pair is superseded |
| capture B | `NULL` | yes | the successor was deleted or left the session |
| `NULL` | `NULL` | no | last capture in the session; there is no forward transition |

Everything the design needs follows from this one comparison. Running the pass twice with nothing
changed finds no outstanding transitions and performs no writes. A capture arriving in the middle
of an evaluated pair makes exactly two transitions outstanding and retires one. A capture being
deleted makes its predecessor outstanding. Re-grouping a deployment's captures into different
sessions (`group_images_into_events`, which is now operator-configurable) changes which captures
are adjacent, and the boundary captures become outstanding without anything having to know that
regrouping happened.

The marker is deliberately not derived from `Detection.next_detection`. A transition that was
evaluated and produced no links is indistinguishable from a transition never evaluated if links
are the only record, so a link-derived marker would re-do the expensive matching for every
transition that legitimately matched nothing — which, given the cost threshold, is likely to be
most of them.

There is a second, push-based half to the marker. When results are saved for a capture, that
capture's detections change, so any transition touching it is stale even if adjacency did not
move. `save_results` therefore clears `tracking_successor` on the capture it just processed and on
the processed capture immediately before it in the session. This is what makes re-processing a
capture with a different pipeline safe, and it is a two-row `UPDATE` found through the existing
`(event, timestamp)` index.

### Finding the outstanding transitions

```python
processed = Exists(Detection.objects.filter(source_image_id=OuterRef("pk")))
rows = (SourceImage.objects
        .filter(event_id=event_id).filter(processed)
        .order_by("timestamp", "pk")
        .values_list("pk", "tracking_successor_id"))
```

The successor of each row is the next row, computed in Python over a list of at most a few
thousand tuples. Measured with `EXPLAIN (ANALYZE, BUFFERS)` against the local database, expressed
in SQL with a `lead()` window function so the whole comparison happens in the database:

- Session with 4,497 captures, 750 processed: **34 ms cold, 6.5 ms warm.**
- Session with 23,362 captures, 65 processed: **291 ms cold, 18 ms warm** (three consecutive runs
  at 18.19 / 18.20 / 18.28 ms).

The plan is a bitmap index scan on the existing `main_source_event_i_ab7d5d_idx` over `event_id`,
feeding a nested-loop semi-join whose inner side is an index-only scan on
`main_detection_source_image_id_883797a1`. The cost is therefore bounded by the session's *total*
capture count, because the semi-join probes once per capture — not by the processed count. That is
the honest characterisation, and it is why the larger session is slower despite having fewer
processed captures. If it ever becomes hot, the lever is a denormalised processed flag on
`SourceImage`, which would make the scan bounded by the processed count instead. It is not worth
paying for now.

What this query deliberately avoids is the expensive part. Loading a detection's feature embedding
is one query returning a 2,048-dimension `pgvector` column measured at 3,279 bytes per row, and
`get_feature_vector` issues one such query per detection
(`ami/ml/post_processing/tracking_task.py:175`). Processed captures in the largest session average
14.8 detections each (p95 23, max 31, measured), so a single transition costs roughly 30 embedding
queries and 100 KB of vector data, and roughly 225 cost computations. Those numbers are measured;
the resulting estimate that a full batch pass over a 750-capture session issues on the order of
22,000 embedding queries is inferred from reading the code, not profiled. Incremental evaluation
replaces that with two transitions per newly arrived capture.

### The pass

For one session, inside a per-session lock and one transaction:

1. Build the processed sequence and derive the outstanding transitions.
2. If there are none, return. This is the idempotent path and it does no writes.
3. Determine the frozen detections: those belonging to an occurrence with `grouping_verified_at`
   set. They are excluded from matching and from severing.
4. For each outstanding transition `(A, B)` in timestamp order:
   a. Sever stale forward links out of `A` — any detection in `A` whose `next_detection` lives in
      a capture other than `B`, unless either end is frozen.
   b. Run the existing greedy matcher over `A` and `B`, skipping frozen detections.
   c. Set `A.tracking_successor = B` and `A.tracking_evaluated_at = now()`.
5. Reconcile occurrences for every detection touched, so that each maximal chain corresponds to
   exactly one occurrence.
6. Report counters on the job stage.

### Worked example

Take the user's scenario. Session `E`; captures are written `P8` for 8:00pm and so on. Detections
are `d1…`; occurrences `O1…`. Every detection starts in an occurrence of its own, because
`create_and_update_occurrences_for_detections` creates one per detection at result-saving time
(`ami/ml/models/pipeline.py:908`).

**Step 0 — captures at 8:00pm and 9:00pm are processed.**
`P8` gets `d1, d2`; `P9` gets `d3, d4`. Occurrences `O1={d1}`, `O2={d2}`, `O3={d3}`, `O4={d4}`.
No capture has a recorded successor.

**Step 1 — first pass.**
Processed sequence is `[P8, P9]`. `P8` has no recorded successor but its actual successor is `P9`,
so that transition is outstanding. `P9` has neither a recorded nor an actual successor, so it is
not. One transition to evaluate.

Say the matcher accepts `d1↔d3` and rejects everything else. Links: `d1.next_detection = d3`.
Marker: `P8.tracking_successor = P9`.

Reconciling, the maximal chains are `[d1, d3]`, `[d2]` and `[d4]`. The first spans two
occurrences, `O1` and `O3`, so they merge into `O1`. State afterwards:

| | Detections | Links | Occurrences |
|---|---|---|---|
| after step 1 | d1 d2 d3 d4 | d1→d3 | O1={d1,d3}, O2={d2}, O4={d4} |

**Step 2 — run it again immediately.**
`P8.tracking_successor` is `P9`, which is still its actual successor. `P9` still has none. Zero
outstanding transitions, zero writes, nothing loaded. This is the property the whole design
exists for.

**Step 3 — captures at 8:10pm and 8:20pm arrive and are processed.**
`P810` gets `d5`; `P820` gets `d6, d7`, each in a fresh occurrence. Saving those results clears
`tracking_successor` on `P810`, on `P820`, and on the processed capture preceding each — which
includes `P8`. Even without that push, `P8`'s recorded successor `P9` no longer matches its actual
successor `P810`, so the mismatch alone would have caught it.

Processed sequence is now `[P8, P810, P820, P9]`, and three transitions are outstanding:
`(P8, P810)`, `(P810, P820)`, `(P820, P9)`. The pair `(P8, P9)` is not re-evaluated and not marked
stale — it has simply left the sequence, because `P9` is no longer what follows `P8`.

Evaluating in order:

- `(P8, P810)`: first sever stale links out of `P8` — `d1.next_detection` is `d3`, which is in
  `P9`, not `P810`, so it is cleared. Then match: `d1↔d5` accepted, giving `d1→d5`.
- `(P810, P820)`: `d5↔d6` accepted, giving `d5→d6`.
- `(P820, P9)`: `d6↔d3` accepted, giving `d6→d3`. `d7` matches nothing.

Markers become `P8→P810`, `P810→P820`, `P820→P9`. Reconciling, the maximal chain is
`[d1, d5, d6, d3]`, spanning `O1` (which holds both `d1` and `d3`), `O5` and `O6`. They merge into
`O1` — identifications on `O5` and `O6` are reassigned to `O1` before the emptied occurrences are
deleted.

| | Detections | Links | Occurrences |
|---|---|---|---|
| after step 3 | d1 d2 d3 d4 d5 d6 d7 | d1→d5→d6→d3 | O1={d1,d5,d6,d3}, O2={d2}, O4={d4}, O7={d7} |

**Step 3, the branch that forces a split.** Suppose instead that `(P820, P9)` accepts nothing. The
maximal chain is `[d1, d5, d6]`, but `d3` is still a member of `O1` from step 1, and no link
connects it to the rest. Reconciliation must move `d3` out to an occurrence of its own. A
merge-only reconciler — which is what `assign_occurrences_from_detection_chains` is today — would
leave `O1={d1,d5,d6,d3}` and silently assert that a detection at 9:00pm belongs to a track that
ends at 8:20pm.

| | Detections | Links | Occurrences |
|---|---|---|---|
| after step 3, no match at the end | d1 … d7 | d1→d5→d6 | O1={d1,d5,d6}, O8={d3}, O2, O4, O7 |

**Step 3, the branch where a person got there first.** Suppose that between step 1 and step 3
someone verified `O1={d1,d3}` as correctly grouped. Then `d1` and `d3` are frozen: `d1` is not
offered to the matcher as a source, `d3` is not offered as a target, and the stale `d1→d3` link is
not severed. The three transitions are still evaluated for the remaining detections, and the
markers are still set, so the session does not stay permanently outstanding. `O1` is untouched, and
the pass reports that a verified occurrence in this session predates captures that have since
arrived, so a person can decide whether to re-open it. The system does not overwrite the answer a
person gave; it tells them the question changed.

## The seven hard parts

### 1. Adjacency is a moving target

**The mechanism.** A superseded transition is never "invalidated" as such — it stops existing,
because the sequence is derived rather than stored. The recorded successor of the capture before
the insertion point no longer matches, which makes exactly one new transition outstanding on each
side of the arrival.

What must be broken is the *detection-level* link that crossed the now-superseded gap, and here
the existing matcher already handles two of the three cases. `pair_detections` detaches any
existing inbound link to a detection it is about to claim
(`ami/ml/post_processing/tracking_task.py:332`), and it overwrites the source detection's
`next_detection` when it makes a new match. So if `d1` matches something in the newly inserted
capture, the stale link is overwritten; and if something in the inserted capture matches `d3`,
`d3`'s stale inbound link is detached. The gap is the third case: **`d1` matches nothing in the
inserted capture and nothing in the inserted capture matches `d3`.** The link `d1→d3` then
survives, skipping a capture, and nothing will ever look at it again, because the transition it
belonged to is no longer in the sequence.

The rule is therefore: before evaluating an outstanding transition `(A, B)`, clear every forward
link out of `A`'s detections that does not land in `B`. This is safe to state as an unconditional
rule because a link out of `A` that lands anywhere but `A`'s current successor is by construction
a link across a gap that was closed.

**The alternative I rejected.** Keep the skip link, on the argument that it bridges a frame where
the insect was occluded or the detector missed it, and that bridging is better tracking. I rejected
it because the cost that justified the link described a transition that no longer exists — the two
detections are now two frames apart, and the geometry terms in the cost function are the ones most
sensitive to elapsed time. Keeping it would also mean the link's correctness depends on the order
captures happened to be uploaded, which is not a property anyone can reason about. Gap-tolerant
matching is a real and probably desirable feature — match each capture against the next *k*
processed captures rather than only the next one — but it should be a deliberate, uniformly applied
policy, not a side effect of arrival order.

**One case where the rule must yield.** If either end of the stale link is frozen by a verified
occurrence, the link is left alone; see hard part 4.

### 2. Bookkeeping without a new table

**The mechanism.** Two nullable columns on `SourceImage`, as above. No new model. `SourceImage` is
already the natural home: adjacency is a property of captures, the sequence query reads that table
anyway, and the model already carries derived fields of this kind such as `detections_count`.

`Detection.next_detection` alone is not sufficient, for the reason the brief anticipates. It is
worth being concrete about the cost of getting this wrong: with the current threshold most
transitions are expected to produce no links at all, so a link-derived marker would re-run the
expensive embedding fetch and matching for nearly every transition on every pass, and the
"idempotent" claim would be false in the only sense that matters.

**Migration.** `main_sourceimage` holds 14.8 million rows in 18 GB in the local copy (measured), so
the shape of the migration matters. Both columns are nullable with no default, which PostgreSQL 11
and later add as a catalogue-only change with no table rewrite. The one thing to avoid is the index
Django creates for a `ForeignKey` by default, which would build over the whole table under an
`ACCESS EXCLUSIVE`-adjacent lock. It is not needed: the only reverse question the design asks is
"which capture precedes this one", and that is answered by timestamp order through the existing
`(event, timestamp)` index rather than by following the marker backwards. Hence `db_index=False`.

```python
# ami/main/migrations/0100_sourceimage_tracking_markers.py
class Migration(migrations.Migration):
    dependencies = [("main", "0099_occurrence_grouping_verification")]
    operations = [
        migrations.AddField(
            model_name="sourceimage",
            name="tracking_successor",
            field=models.ForeignKey(
                "self", null=True, blank=True, db_index=False,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tracking_predecessors",
            ),
        ),
        migrations.AddField(
            model_name="sourceimage",
            name="tracking_evaluated_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
```

`on_delete=SET_NULL` is load-bearing rather than incidental: deleting a capture nulls the marker on
its predecessor, which makes that predecessor outstanding, which is exactly the re-evaluation the
deletion should trigger.

**The alternative I rejected.** A `TrackedTransition` table with `(from_capture, to_capture,
evaluated_at, links_created, config)` and a uniqueness constraint on the pair. It is more
expressive — it can record how a transition was evaluated, not just that it was — but it holds
roughly one row per processed capture, which on a table already at 14.8 million captures is a
second large table to write, index, vacuum and reason about, in exchange for information only a
diagnostic would read. The two columns carry the whole decision.

**A related knob I also rejected.** Storing a fingerprint of the tracking configuration alongside
the marker, so that changing `cost_threshold` makes every transition outstanding again. It is
tempting and it is arguably correct, but it means a routine change to a project default silently
re-tracks every session, including re-deciding groupings a person has been looking at. The operator
job instead gets an explicit "re-evaluate from scratch" option that clears the markers for a chosen
scope, so re-tracking after a configuration change is a decision somebody makes rather than a
consequence they discover.

### 3. Merging occurrences must not destroy identifications

**The mechanism.** This one is already solved in the working tree by a parallel change, and the
right answer is to use it rather than to write a second one. `ami/main/models_future/tracks.py`
now carries `_absorb(target, sources)`, which reassigns `Identification.occurrence` to the survivor
*before* deleting the emptied occurrences, precisely because `Identification.occurrence` cascades.
`merge_occurrences(target, sources)` wraps it with a same-session check. The reconciler calls
`merge_occurrences` and never issues `Occurrence.objects.delete()` of its own.

The current batch reconciler does the opposite: it deletes sibling occurrences directly
(`ami/ml/post_processing/tracking_task.py:256`) with a comment explaining that the fresh-event
guard makes this safe. Removing the guard removes that safety, so this call site has to change in
the same commit that removes `require_fresh_event`. These two edits are a pair; splitting them
across commits leaves a window in which the code silently destroys human work.

**Choosing the survivor.** Among the occurrences a chain spans, prefer the one carrying
non-withdrawn identifications; break ties on the earliest detection timestamp and then on the
lowest primary key, so the choice is deterministic and a re-run picks the same survivor.

**When not to merge at all.** If two or more of the occurrences in a chain carry non-withdrawn
identifications, merging them asserts that two people who each labelled a distinct animal were
labelling one animal. The pass refuses: it cuts the chain link at the boundary between them, counts
the refusal, and logs it. Because the transition's marker is set and the matcher is deterministic,
the cut is stable — a later pass will not re-create it unless a capture arrives in that gap, in
which case it re-evaluates and re-cuts, reaching the same state. **The alternative I rejected** was
to compare the identifications' taxa and merge when they agree. That is better behaviour in the
common case, but it needs a definition of agreement across ranks — a genus-level identification and
a species-level one below it do not conflict — and getting that wrong destroys exactly the data
this rule exists to protect. Refusing whenever two identified occurrences would combine is the
conservative reading, and it matches the bias `tracks.py` already states in its module docstring:
leave one animal as two occurrences rather than merge two animals into one.

### 4. Human edits must survive

**The mechanism.** Two records, both of which now exist in the working tree.

The first is the invariant the human track operations already enforce: *a chain link never crosses
an occurrence boundary*. `_cut_links_leaving` clears both outbound and inbound links that would
escape an occurrence after any operation that moves detections. This is what makes a human split
durable against a merge-only reconciler — the reconciler walks chains, and after a split there is
no chain connecting the two halves, so nothing invites it to fold them back together.

The second is `Occurrence.grouping_verified_at` / `grouping_verified_by`, set only by the explicit
`verify_grouping` call and cleared by any operation that changes an occurrence's detection set.
This is the stronger record: it means a person looked at this exact set of detections and confirmed
it. The tracking pass treats a verified occurrence as frozen — its detections are excluded from
matching in both directions, its links are not severed, and it is never a merge source or target.

Freezing at the occurrence level rather than the session level is the important change from the
current design. `skip_if_human_identifications` today refuses a whole session as soon as one
occurrence in it carries an identification (`ami/ml/post_processing/tracking_task.py:522`), which
in a session with hundreds of occurrences means one person's single click permanently stops
tracking for everything else in that night. Per-occurrence freezing keeps the protection and drops
the collateral damage.

**A verified occurrence in a session that later gains captures is a reported condition, not a
silent one.** The pass counts these and names them in the job stage metrics, so the natural
follow-up — a review queue of occurrences whose evidence changed after they were confirmed — has
the data it needs. Given that the stated priority is building a human-verified test set, an
occurrence whose ground truth may have gone stale is exactly the kind of thing that should be
surfaced rather than either overwritten or quietly left.

**The alternative I rejected.** A per-detection `curated_at` timestamp meaning "a person edited
this detection's track membership", checked by the matcher. It is a single column and it is
finer-grained. I rejected it because it records the wrong thing: it captures that an edit happened,
not what the person asserted. The occurrence-level verification says "this set is right", which is
both the thing tracking must not contradict and the label the tracking methods will be scored
against. Detection-level pinning would also freeze detections out of all future tracking forever,
including in sessions where the person's edit had nothing to do with the transition being
evaluated.

### 5. Concurrency

**The mechanism.** Three layers, in increasing narrowness.

*Session-level exclusion, tracking against tracking.* Reuse the pattern already in this codebase:
`_regroup_lock` at `ami/main/models.py:1476` is a token-released, TTL-capped cache lock keyed by
deployment, whose caller short-circuits when it is already held. A `_tracking_lock(event_id)` in the
same shape gives the same semantics per session. The short-circuit is safe here in a way it usually
is not, and this is the design's best property: **because outstanding-ness is derived state rather
than a queue, work that is skipped is never lost, only deferred.** A pass that cannot get the lock
returns without doing anything, and the transitions it did not evaluate are still outstanding for
whoever runs next.

*Result-arrival debouncing.* Several captures from the same session finish in parallel workers, and
each would otherwise enqueue a pass. `save_results` enqueues `track_event_incrementally` with a
short countdown, guarded by a `cache.add` dedup key on the session with a TTL matching the
countdown — the same idiom the job heartbeat endpoints use (`ami/jobs/views.py:79`). Many arrivals
collapse into one pass, which is also what makes the pass efficient: it sees all the new captures
at once and evaluates each transition once.

*Row-level exclusion, tracking against people.* The cache lock does not protect against a person
calling `split_track` while a pass is running, and it cannot, because a cache lock is not
transactional and a hard worker death leaves it held until the TTL. `Detection.next_detection` is
`UNIQUE`, so two writers assigning the same target raise `IntegrityError`. The prescription is that
both sides take `select_for_update()` on the detections they are about to modify, ordered by
primary key so two writers cannot deadlock against each other. For the tracking pass that is the
detections of the two captures in the transition, on the order of thirty rows. For the human
operations it is the occurrence's detections, which they already materialise in
`_ordered_detections`. This is a small addition to `tracks.py` and it should land with this work,
because today those operations take no row locks at all.

**Retry semantics.** A skipped session needs no retry: the next trigger or the periodic sweep picks
it up, and correctness does not depend on when. A genuine `IntegrityError` on `next_detection` means
a writer outside the lock got there first; retry the session once after a short backoff, and on a
second failure fail the job with the reason rather than retrying indefinitely, because a persistent
conflict means an assumption is wrong and a loop would hide it. The per-session transaction means a
failure rolls back that session and leaves its markers unset, so the work is retried in full and
never half-recorded.

**The alternative I rejected.** A PostgreSQL advisory transaction lock, `pg_try_advisory_xact_lock`,
keyed on the session. It is strictly better than a cache lock — it is transactional, it releases on
rollback, and it cannot be orphaned by a killed worker. I still recommend the cache lock, because
the codebase already has one implementation of exactly this pattern with its failure modes
documented in a docstring, and having one locking idiom that everybody recognises is worth more here
than the correctness margin. If the advisory lock is preferred, it should replace `_regroup_lock`
too, as a separate change.

### 6. Cost and scale

Covered in "Finding the outstanding transitions" above, but to answer the question directly: the
query that finds outstanding work is a single indexed scan of one session's captures with a
semi-join against detections, measured at 6.5 ms warm and 34 ms cold on the session with the most
processed captures, and 18 ms warm and 291 ms cold on the session with the most captures. It is
bounded by the session's total capture count. I have not verified any claim beyond these two
sessions, and I have not measured the pass end to end, because the local database holds only 324
classifications with feature embeddings — far too few to time a realistic matching run.

The part that matters is what the pass *does not* do. It never loads a feature embedding for a
transition it is not evaluating, and after the first pass over a session the number of transitions
it evaluates is two per newly arrived capture rather than one per capture in the session. On the
750-capture session that is the difference between roughly 22,000 embedding queries and roughly 60
— the first figure inferred from reading `get_feature_vector` and the per-capture detection counts,
not profiled.

One bound worth stating explicitly because it is not obvious: the reconciliation step walks maximal
chains, and a chain can extend outside the window of captures the pass evaluated. The reconciler is
therefore a fixpoint over a work-set of detections rather than a loop over a fixed list — seed it
with the detections of the evaluated transitions plus the detections of every occurrence those
touch, and process chains until the set is empty. Chain length is bounded by how long an insect
stays on the sheet, which at one processed capture per minute could be hundreds of frames. I have
not measured chain lengths, because no production data has been tracked yet; see the last section.

### 7. The trigger

**The recommendation.** Fire from the tail of `save_results`, into a debounced per-session Celery
task, gated by a project-level setting that is off by default. Keep the operator-triggered
post-processing job for explicit and configuration-changing runs. Add a periodic sweep as a
backstop, restricted to sessions whose captures changed in the last day.

`save_results` is the right place because it is the only point that knows a capture has just become
processed, and both the synchronous and asynchronous result paths funnel through it
(`ami/ml/models/pipeline.py:1016`). It is also where the per-detection occurrences are created, so
tracking runs immediately after the state it consumes is written.

**Why not a signal.** A `post_save` signal on `Detection` would fire once per detection — thousands
per batch — and, decisively, it would not fire at all: `create_and_update_occurrences_for_detections`
uses `bulk_create` and `bulk_update` (`ami/ml/models/pipeline.py:946`), and neither sends model
signals. A signal-based trigger would silently never run.

**Why not the periodic sweep alone.** Finding outstanding transitions across all sessions means the
sequence query without an `event_id` filter, which is a scan of the whole capture table rather than
one session's slice, and it puts minutes of latency between a capture being processed and its
occurrence appearing correctly grouped in the interface. As a backstop scoped to recently-changed
sessions it is cheap and worth having, because it recovers sessions whose results landed while
tracking was disabled, failing, or losing the lock.

**Why gate it off by default.** Tracking changes occurrence grouping, which changes occurrence
counts, taxa counts and what the gallery shows. The cost threshold is documented in the code as
calibrated against synthetic features in tests, and the measurement above suggests it may not link
anything at all on real sampled sessions. Turning it on per project, after somebody has looked at
what it does to that project's sessions, is the difference between a feature and an incident. The
tradeoff is real and worth naming: a default-off switch means most projects get no benefit until
somebody makes a decision, and the automatic path will be less exercised, so bugs in it will surface
later. I still recommend it, and I would revisit the default once there is a verified test set to
score against.

## What changes in the code

| File | Shape of the change |
|---|---|
| `ami/main/models.py` | Two fields on `SourceImage`: `tracking_successor` (self-FK, `db_index=False`, `SET_NULL`) and `tracking_evaluated_at`. |
| `ami/main/migrations/0100_sourceimage_tracking_markers.py` | New migration, as above. Two `AddField`s, no rewrite, no index build. |
| `ami/ml/post_processing/tracking_task.py` | The substantial rewrite. `assign_occurrences_by_tracking_images` is replaced by a pass over outstanding transitions. `event_is_fresh` and `event_fully_processed` are deleted. `pair_detections` gains a `skip_detection_ids` parameter; its body is otherwise unchanged. The caller gains the stale-link severing step. `TrackingConfig` loses `require_fresh_event`, `require_completely_processed_session` and `skip_if_human_identifications` as *behaviour* — see the note below — and gains `reset_scope: bool = False`. |
| `ami/ml/post_processing/tracking_reconcile.py` | New. The chain-to-occurrence reconciler: fixpoint over a detection work-set, merge and split, delegating all occurrence deletion to `merge_occurrences`. |
| `ami/main/models_future/tracks.py` | Promote `_absorb`, `_cut_links_leaving` and `_clear_verification` to public names so the reconciler can use them. Add `select_for_update()` on the detections each operation modifies, ordered by primary key. |
| `ami/ml/models/pipeline.py` | At the tail of `save_results`: clear the tracking markers for the processed captures and their predecessors, then enqueue the debounced pass per affected session. |
| `ami/ml/tasks.py` | New `track_event_incrementally(event_id)` shared task holding `_tracking_lock`. |
| `ami/main/models.py` (lock helper) | `_tracking_lock(event_id)`, modelled on `_regroup_lock` at line 1476. |
| `ami/main/models_future/projects.py` | A boolean on `ProjectSettingsMixin` enabling automatic tracking, defaulting to off — the same place `session_time_gap_seconds` and the default filters live. Adds a second small migration. |
| `config/settings/base.py` | Beat entry for the recently-changed-sessions sweep. |
| `ami/ml/post_processing/admin/tracking_form.py` | Drop the "only track untracked sessions" and "skip sessions with human identifications" knobs; add "re-evaluate from scratch". |
| `ami/ml/post_processing/tests/test_tracking_task.py` | New cases; see below. |

**A note on removing config fields.** `TrackingConfig` sets `extra = "forbid"`
(`ami/ml/post_processing/tracking_task.py:61`), and existing `Job.params` rows carry the removed
field names. Deleting the fields outright makes those jobs fail to re-run with a validation error.
Keep the three fields declared, ignored, and marked deprecated in their comment, and remove them in
a later release once no live job params reference them.

**Tests worth writing, in the order they matter.** Running the pass twice writes nothing the second
time (the core claim). A capture arriving between two evaluated captures produces exactly two
outstanding transitions and severs the skip link. A chain that stops mid-way splits the trailing
detection out of the shared occurrence — the branch a merge-only reconciler gets wrong. A merge
moves identifications to the survivor and the survivor still has them after the source is deleted.
A verified occurrence is untouched by a pass over a session that gained captures, and the pass
reports it. Two identified occurrences are not merged. A second pass holding the lock returns
without writing, and the transitions it skipped are still outstanding afterwards.

## What stays the same

The cost function survives untouched: `total_cost`, `cosine_similarity`, `iou`, `box_ratio`,
`distance_ratio` and `image_diagonal` are unchanged, and so is the meaning of `cost_threshold`.

The greedy claim-set matching survives. `pair_detections` keeps its structure — build candidates
below threshold, sort by `(cost, det.pk, nxt.pk)` for determinism, then claim greedily with one
partner per detection on each side. It gains one parameter, a set of detection ids to skip, and its
existing inbound-detach step turns out to be exactly right for the insertion case. The determinism
of the tie-break is more load-bearing in this design than in the batch one: it is what makes
re-evaluating a transition produce the same answer, which is what makes a refused merge stable
rather than flapping.

The chain-walk primitive survives as a primitive — follow `next_detection` forward, follow
`previous_detection` back to find the head. What does not survive is the reconciler built around it.
`assign_occurrences_from_detection_chains` merges only, deletes occurrences directly, and takes a
list of source images as its scope. All three have to change: it must split as well as merge, it
must delegate deletion to `merge_occurrences` so identifications move first, and its scope must be a
work-set of detections that can follow chains beyond the captures the pass evaluated. It is honest
to call this a rewrite rather than an adaptation.

`get_unique_feature_algorithm_for_event`, `get_feature_vector`, the `TrackingTask` shell, the
post-processing job framework, the admin action machinery and both entry points (capture set and
Events changelist) are unchanged.

## What I am unsure about

**Whether the cost threshold links anything at all on real sessions, which would make this design
correct and useless at the same time.** The gap between adjacent processed captures is 45 to 600
seconds (measured), and `total_cost` sums `(1 - IoU)` among its terms. Two boxes that do not overlap
contribute 1.0 from that term alone, which already exceeds the default threshold of 0.2, so on this
data the matcher would link only insects that barely moved in a minute. This is inferred from
reading the cost function, not measured, but it is a strong enough inference that I would settle it
before building anything. *The experiment:* take one session with embeddings, compute the full cost
matrix for every adjacent processed pair, and plot the distribution of the minimum cost per
detection against the time gap. If the mass sits above 0.2, the threshold — or the cost function's
weighting of geometry against appearance — needs work before incremental evaluation is worth having.

**Whether severing the skip link improves or degrades grouping.** I argued for severing on
principle, but it is an empirical question and the principle could be wrong. *The experiment:* once
there is a set of `grouping_verified` occurrences, run both policies over the same sessions with
captures deliberately withheld and then added, and score each against the verified groupings. This
is the first thing the verified test set should be spent on.

**Whether the reconciler's chain walk is bounded in practice.** Chain length is bounded by how long
an insect stays in frame, which nobody has measured because no production data has been tracked. If
chains routinely run to hundreds of detections, walking one per pass per touched detection is more
expensive than I have assumed. *The experiment:* after the first real tracking run, record the
distribution of detections per occurrence, and if the tail is long, cap the walk and reconcile in
batches keyed on occurrence rather than on chain.

**Whether per-session locking is granular enough.** A session is a night; a pass over one that has
just gained a thousand captures could hold the lock for minutes while other passes for the same
session are dropped. Dropping is safe, but it could mean a busy session's tracking lags behind its
results indefinitely. *The experiment:* instrument the pass with the number of transitions evaluated
and the wall time, and watch whether the dedup key ever expires with work still outstanding. If it
does, the fix is to evaluate outstanding transitions in bounded chunks and re-enqueue, which the
marker makes safe to do at any point.

**Whether automatic triggering should be gated per project or per deployment.** I recommended per
project because that is where `ProjectSettingsMixin` already collects settings of this kind, but sampling rates are a
property of how a station is operated, and the measurement above shows they vary between sessions
within what may be the same project. *The experiment:* check whether processed-capture gaps cluster
by project or by deployment across the local database; if by deployment, the setting belongs there.
