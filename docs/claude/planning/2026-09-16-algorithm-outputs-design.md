# Storing algorithm outputs that are not species classifications

Status: design, not yet implemented. Date: 2026-09-16.

## Summary

Antenna can currently only record one kind of machine learning output: a species
classification. Anything else a model produces — a feature vector, a size estimate, a body
pose, a caption — has to be squeezed onto a classification row, and a classification row is
not inert: it competes to become the occurrence's name. This document proposes a small set
of tables that share one common shape ("an algorithm produced this, about this thing, at
this time"), a typed table for each output the platform actually acts on, and one
JSON-backed table for everything else and for experiments. The first of these tables,
`DetectionEmbedding`, already exists on a local branch and is empty everywhere, so the
cheapest moment to settle the shape is now.

## Problem

Today every model output is bolted onto `Classification` (`ami/main/models.py:3022`). That
one row carries the prediction itself (`taxon`, `score`, `terminal`, at
`ami/main/models.py:3033-3038`), the full raw output of the network (`logits` and `scores`,
two `float8[]` arrays, `ami/main/models.py:3039-3046`), and the backbone feature vector
(`features_2048`, a fixed 2048-dimension pgvector column, `ami/main/models.py:3047`).

Three consequences follow.

**A classification is never inert.** `Occurrence.predictions()`
(`ami/main/models.py:3952`) selects the highest-scoring classification per algorithm, and
`best_prediction` (`ami/main/models.py:3919`) then orders those by `-terminal, -score`. Any
extra classification row can therefore change an occurrence's determination, including one
written only because it was the sole place a vector could be stored. This is not
theoretical: it has already bitten in fixtures, where a non-terminal probe classification
outscored the terminal label and silently took over the determination. So storing a vector
for a crop the moth/non-moth filter rejected — exactly the crops appearance-based tracking
most needs — is unsafe on the classification table.

**The hot row is not hot.** Measured on the local copy of the production database:
`main_classification` holds 834,193 rows in a 118 MB heap (about 148 bytes per row), 103 MB
of indexes, and **4,278 MB of TOAST** — roughly 36 times the heap. 307,663 rows carry
logits and 309,079 carry softmax scores, so the arrays cost about 14 KB per array-bearing
row on disk after TOAST compression. The vector is a further ~8 KB per row when present
(522 rows today). These columns are almost never wanted, but they are easy to drag into a
query by accident: `.distinct()` on a classification queryset sorts the arrays and turned a
0.5 s `COUNT` into 208 s on 55,530 rows, and `.defer("features_2048")` does not reach the
second copy of the table introduced by a `select_related("applied_to")` self-join.

**The vocabulary exists; the storage does not.** `AlgorithmTaskType`
(`ami/ml/models/algorithm.py:202-221`) already names `embedding`, `size_estimation`,
`pose_estimation`, `depth_estimation`, `regression`, `captioning` and `tracking`. A
processing service can declare itself as any of those today. There is nowhere for the
result to land.

`DetectionEmbedding` (`ami/main/models.py:3429`) is the first output moved out. This design
generalises from it rather than treating it as a one-off.

## Design

The shape chosen is a shared abstract spine, typed tables for outputs the platform acts on,
and one generic JSON table for the long tail. The catalogue below says which kind of output
goes where; the sections after it define the tables it names.

### 1. Output kinds

`AlgorithmTaskType` (`ami/ml/models/algorithm.py:202-221`) already enumerates the kinds of
model output the platform expects, and it is what a processing service declares itself as.
Reusing it as the catalogue of output kinds means one vocabulary rather than two, and the
routing rule becomes simply "task type chooses the table". `outputs[].type` on the wire
carries these same values (see the wire contract below), and because an algorithm's
`task_type` is registered, an output whose type contradicts it can be caught on arrival.

| Task type | Output shape and example | Attaches to | Home | Affects determination |
| --- | --- | --- | --- | --- |
| `detection` | Box and score, `[0.12, 0.44, 0.31, 0.58]`, `0.87` | capture | `Detection`, existing | No |
| `localization` | Box or point, as above | capture | `Detection`, existing | No |
| `segmentation` | Mask polygon, RLE string, or a mask image URL | detection | Generic JSON | No |
| `classification` | Label, score, full logits, `Noctua pronuba`, `0.94` | detection | `Classification` + `ClassificationScores`, existing | **Yes** |
| `embedding` | Float vector, 512 / 768 / 2048 wide | detection | Vector table, existing | No |
| `tracking` | Link between two detections, or a track identifier | occurrence | `Occurrence`, `Detection.next_detection`, existing | No |
| `tagging` | Non-taxon labels and scores, `["worn", "male"]` | detection | New typed table, early; see the note below | No |
| `regression` | Scalar with unit and uncertainty, `0.42 g ± 0.05` | detection | `DetectionMeasurement`, new typed table, early | No |
| `size_estimation` | Scalar with unit, `24.5 mm wingspan` | detection | `DetectionMeasurement`, new typed table, early | No |
| `depth_estimation` | Depth map URL, or a scalar distance | detection or capture | Generic JSON for a map, `DetectionMeasurement` for a scalar | No |
| `pose_estimation` | Keypoint list, `[{name, x, y, score}, …]` | detection | Generic JSON | No |
| `captioning` | Free text, `"a moth resting on a white sheet"` | detection or capture | Generic JSON | No |
| `generation` | URL to a generated image, or text | detection or capture | Generic JSON | No |
| `translation` | Text in another language | any | Generic JSON | No |
| `summarization` | Text summarising a capture or a night | capture or occurrence | Generic JSON | No |
| `question_answering` | Question and answer text | any | Generic JSON | No |
| `post_processing` | Varies; today it rewrites a classification | detection | `Classification` via `applied_to`, existing | Yes, by construction |
| `other` | Anything | any | Generic JSON | No |
| `unknown` | Anything, from a service that did not declare itself | any | Generic JSON | No |

Only `classification` reaches the determination, and `post_processing` only because it
produces classifications on purpose. Everything else is inert by construction, which is the
property this whole design exists to give us.

**Tagging needs a decision.** A tag is a label that must not compete for the name — "worn",
"male", "in copula". Storing it as a `Classification` with a non-taxon category map is
tempting because the scoring machinery already exists, but `Occurrence.predictions()`
(`ami/main/models.py:3952`) does not exclude classifications with a null taxon, so a
high-scoring tag would be returned by `best_prediction` exactly as a species label is. The
recommendation is a small typed table of its own, sharing the spine, with a label and a
score. That is a reading of the code rather than a tested claim, and worth confirming
before building either version.

### 2. The spine: an abstract `AlgorithmOutput` base model

An abstract Django model (no table of its own) that every output table inherits, so the
provenance fields are named and typed identically everywhere and a reader can be written
once against the shape.

| Field | Type | Notes |
| --- | --- | --- |
| `detection` | FK `Detection`, `null=True`, `CASCADE` | One of the three targets |
| `source_image` | FK `SourceImage`, `null=True`, `CASCADE` | Capture-level outputs |
| `occurrence` | FK `Occurrence`, `null=True`, `CASCADE` | Occurrence-level outputs |
| `algorithm` | FK `ml.Algorithm`, `CASCADE` | Which model produced it |
| `timestamp` | `DateTimeField` | When the model produced it |
| `job` | FK `jobs.Job`, `null=True`, `SET_NULL` | Which run wrote it, for auditing |
| `created_at`, `updated_at` | inherited from `BaseModel` (`ami/base/models.py:91`) | |

A check constraint on each concrete table requires exactly one of the three targets to be
non-null.

Two honest complications. First, `get_project_accessor()` (`ami/base/models.py:99`) is a
classmethod returning a single path, so a table that genuinely mixes targets has no single
project accessor and would not filter correctly for permissions; the recommendation is that
each of the first tables targets exactly one thing and declares its own accessor, as
`Classification` and `DetectionEmbedding` both already do. Second, `Classification` has no
`job` field today (there is a commented-out one at `ami/main/models.py:3060`), so adopting
the spine adds a nullable column to the largest of these tables — cheap, but its own PR.

### 3. Typed tables for outputs the platform acts on

An output earns a table when the UI, a filter, or a background job reads individual fields
of it.

| Table | Target | Fields | Status |
| --- | --- | --- | --- |
| `Classification` | detection | `taxon`, `score`, `terminal`, `category_map`, `applied_to` | Exists; stays. It is what determinations read. |
| `ClassificationScores` | — (1:1 off `Classification`) | `logits`, `scores` | New; moves the two arrays off the hot row |
| `DetectionEmbedding` | detection | `vector` | Exists on `feat/detection-embeddings`, empty |
| `DetectionMeasurement` | detection | `kind`, `value`, `unit`, `uncertainty` | Future; the worked example below |

`ClassificationScores` is a side table keyed on the classification (a `OneToOneField` used
as the primary key), not an inheritor of the spine — the arrays belong to one specific
prediction, not to an independent observation. Moving them leaves `Classification` at
roughly its 148-byte heap row and makes the arrays opt-in through an explicit join, which
no accidental `.distinct()` or `select_related` can pull in.

**Decided 2026-09-22: the move also shrinks what is kept and drops what is derivable.**
Two changes ride along with stage (b), because the backfill rewrites every one of these
rows once and there is no reason to rewrite them twice.

*Shrink the logits to four bytes per class.* `logits` is `float8[]`, eight bytes per class,
and a model's raw output does not need double precision. pgvector's `vector` holds
four-byte floats and is already installed, so a dimensionless `vector` column halves the
bytes with no new dependency. Two caveats to settle first: pgvector rejects `NaN` and
infinity where `float8[]` accepts them, which matters because a masked class can legitimately
emit `-inf`; and a `vector` reads back as a numpy array, so every call site of
`top_scores_with_index()` and `predictions()` (`ami/main/models.py:3090-3115`) has to
tolerate that. If the `-inf` check fails, keep `float4[]`, which still halves the bytes.

*Drop `scores` as redundant.* The softmax scores are a pure function of the logits, so
storing both doubles the cost of the most expensive column in the database to save one
cheap computation. Keep `logits`, compute the scores on read.

One caveat that has to be handled in the migration rather than waved past: the two columns
are not populated together. 307,663 rows carry logits and **309,079 carry scores**, so
roughly 1,400 rows have scores with no logits behind them, and for those the scores cannot
be recomputed. Find them first, and either keep their scores or accept the loss knowingly;
do not discover them by deleting the column.

`DetectionMeasurement` is sketched rather than built now. One scalar with a unit covers
wingspan, body length, estimated mass and distance, and it is the kind of output a user
would want to sort and filter on, which is the test for deserving a table.

### 4. One generic table for everything else

| Field | Type | Notes |
| --- | --- | --- |
| (spine fields) | | target, algorithm, timestamp, job |
| `output_type` | `CharField`, indexed | An `AlgorithmTaskType` value; see the catalogue above |
| `data` | `JSONField` (JSONB) | Validated on write against a per-type pydantic schema |

A module-level registry maps `output_type` to a pydantic model, and the save path validates
`data` against it before writing. An unregistered type is stored as-is, so a processing
service experimenting with a new output is never blocked on an Antenna deploy; it simply
gets no validation and no UI until someone registers the type.

**What must not go in here**, stated plainly because the table will otherwise become the
path of least resistance:

- **Vectors and logits.** JSONB stores floats as text, so a 2048-float vector is roughly
  25 KB here against 8 KB as `vector`, it cannot be indexed for similarity, and the "one
  feature extractor per similarity query" rule cannot be enforced on an untyped blob.
- **Anything a user filters or sorts on.** A JSONB expression index is possible but it is a
  per-key decision made after the fact, and it will not be made. Promote the type instead.
- **Anything the determination logic reads.** Determinations read `Classification` and
  nothing else, and that should stay true.

Promotion from generic to typed is the expected lifecycle, not a failure; the generic table
is where a type lives while we find out whether anyone uses it.

### 5. Wire contract

`DetectionResponse` (`ami/ml/schemas.py:204`) gains one generic field beside
`classifications`:

```
outputs: list[AlgorithmOutputResponse] | None
  AlgorithmOutputResponse = { algorithm: AlgorithmReference, type: str, data: dict }
```

`type` carries an `AlgorithmTaskType` value, the same vocabulary a service already uses for
`AlgorithmConfigResponse.task_type` (`ami/ml/schemas.py:101`), and Antenna routes on it
straight from the catalogue in section 1.

Three rules on arrival. An algorithm key the service did not declare in `/info` fails the
whole batch with `PipelineNotConfigured`, as `create_detection_embeddings` already does
(`ami/ml/models/pipeline.py:718-724`). An output whose `type` contradicts its algorithm's
registered `task_type` (`ami/ml/models/algorithm.py:233`) — a classifier sending a pose,
say — is caught here; whether it warns or fails is an open question below. An unrecognised
`type` never fails; it goes to the generic table.

Capture-level and occurrence-level outputs get the same field on their own response models
when a service needs them. None does yet, so that is deferred.

**Recommendation: keep `embeddings` as its own typed field** (`ami/ml/schemas.py:212`)
rather than folding vectors into `outputs`. A vector inside `data: dict` is JSON-encoded
floats, roughly three times the bytes on the wire, with no width check at the boundary —
`EmbeddingResponse` validates the length today (`ami/ml/schemas.py:197-201`), and that is
the only thing between a misconfigured service and a table of unusable vectors. Same
reasoning as the "no vectors in the generic table" rule, applied to the wire.

Whatever is added here, `ami/ml/schemas.py` must stay free of Antenna-side concepts: no
projects, users, or permissions. A task type names a kind of model output, not an Antenna
feature, which is part of why it is safe to share as the routing vocabulary.

### 6. Changes to make to the vector table now, while it is empty

`DetectionEmbedding` exists only on a local branch (migration `0101_detection_embedding.py`)
and holds no rows anywhere. These changes cost nothing today and a data migration later.

1. **Rename `features_2048` to `vector`** (`ami/main/models.py:3442`). The name encodes a
   width that is already wrong for other backbones — 768 and 512 are both common.
2. **Drop the fixed width.** `VectorField()` with no `dimensions` maps to Postgres `vector`,
   which accepts any width in the same column ([pgvector README](https://github.com/pgvector/pgvector)).
   Antenna does not choose the width; the model does.
3. **Validate the width per algorithm.** The proposal is a nullable
   `Algorithm.output_dimensions` integer (`ami/ml/models/algorithm.py:228`), populated from
   a matching field on `AlgorithmConfigResponse`, and checked on write. The category map is
   not the right home: it describes labels, and an embedding algorithm has no labels. This
   is an ML-backend schema addition, which is legitimate because the dimension is a property
   of the model rather than of Antenna.
4. **Keep unique `(detection, algorithm)`** (`ami/main/models.py:3448-3451`) — one vector per
   detection per model, replaced on reprocessing.
5. **Similarity indexes as per-algorithm partial expression indexes with a cast**, which is
   the documented pattern for a dimensionless column:
   `CREATE INDEX ... USING hnsw ((vector::vector(512)) vector_cosine_ops) WHERE algorithm_id = 7`.
   This is also the only index shape consistent with the domain rule that vectors from
   different algorithms are never comparable. Note the caps: an indexed `vector` is limited
   to 2,000 dimensions and an indexed `halfvec` to 4,000, so a 2048-dimension backbone
   cannot be indexed as `vector` and needs `halfvec`, which arrived in pgvector 0.7.0.

   **Decided 2026-09-22: upgrade the extension, and treat 0.7.0 or later as the baseline.**
   This is cheaper than it first looked. Measured on the local stack: the database has
   pgvector **0.5.1** installed while the image already provides **0.8.6**, so the upgrade is
   `ALTER EXTENSION vector UPDATE;` — no image change, no dump, no data migration. Postgres
   itself is 16.15. Two `vector(2048)` columns exist today,
   `main_classification.features_2048` and `main_detectionembedding.features_2048`, and an
   extension update leaves both as they are; `halfvec` simply becomes available for new
   columns.

   With the upgrade assumed, the width question stops being about whether an index is
   possible at all and becomes an ordinary size and quality trade-off: 1024 dimensions costs
   about 4 KB a row against 8 KB at 2048, indexes as a plain `vector` with no `halfvec`
   needed, and scans faster. Choose the width on retrieval quality, not on the extension.

   Confirm the deployed databases before relying on this. Production and staging declare no
   postgres service of their own (`docker-compose.production.yml`,
   `docker-compose.staging.yml`), so their database is managed externally and the upgrade
   there is an operations task rather than an image bump. The local result does not carry
   over to them on its own.

## Sizes and scale

All figures below are **estimates from the storage formats**, except the ones explicitly
marked measured. pgvector stores four bytes per dimension plus an eight-byte header;
`float8[]` stores eight bytes per element plus about 24 bytes of array header.

| Item | Per row | 10 M rows |
| --- | --- | --- |
| `vector`, 2048 dims | ~8.0 KB | ~80 GB |
| `vector`, 768 dims | ~3.0 KB | ~30 GB |
| `vector`, 512 dims | ~2.0 KB | ~20 GB |
| `logits` + `scores`, 29,176 classes, float8 | ~467 KB | ~4.7 TB |
| `logits` + `scores`, 2,497 classes, float8 | ~40 KB | ~400 GB |
| Same at four bytes per class | half the above | half the above |
| `Classification` heap row without arrays or vector | ~148 B (measured) | ~1.5 GB |

Both class counts are real: the local database holds category maps of 29,176 and 2,497
labels (`ml_algorithmcategorymap` ids 51 and 12), along with 5,952, 3,045 and 2,603.

The table overstates disk, because TOAST compresses. Measured on the local production copy:
834,193 classifications, of which 307,663 carry logits, occupy **4,278 MB of TOAST against
a 118 MB heap** — about 14 KB per array-bearing row. Extrapolating linearly (weakly, since
the mix of algorithms would change), 10 M such rows would be roughly 140 GB of TOAST.

The ratio matters more than the absolute size: the arrays are 36 times the heap on the same
table, and they should not sit where an ordinary query can reach them.

## Migration path

Each stage is its own pull request, and each is independently useful.

**(a) Vector table rename and the spine.** Rename `features_2048` to `vector`, drop the
fixed width, add `Algorithm.output_dimensions`, introduce the abstract base and apply it to
`DetectionEmbedding`. No data exists, so there is nothing to backfill. Needs from the
processing services: the dimension declared in the `/info` algorithm config, and
`EmbeddingResponse.features` relaxed from a hard 2048 to a check against it.

Also in (a), two clean-ups on `Detection` itself (`ami/main/models.py:3262-3272`):

- **Drop `Detection.similarity_vector`.** A `JSONField` placeholder from the initial models
  commit with no reader, writer, serializer or processing-service field, and no data: 0 of
  642,729 rows on a copy of production carry a value. One migration, nothing to move.
- **Populate `Detection.detection_score`, and keep it on `Detection`.** The detector's box
  confidence belongs beside the box and the detector's `algorithm`, which already live on the
  detection, so it is not an output-table candidate. Today the column is never written, and
  neither `DetectionResponse` in Antenna (`ami/ml/schemas.py:206-216`) nor in the processing
  service carries a score, so the contract gains an optional `score` on `DetectionResponse`
  on both sides and `create_detections` stores it. Optional, so an older service that omits
  it still works; the column stays null for those rows.

**(b) Logits side table, shrunk, with the scores dropped.** Create `ClassificationScores`,
write to it, and make the read path fall back to `Classification.logits` / `.scores` when
there is no side row. Backfill in batches — 307,663 rows and 4.2 GB of TOAST is not an
instant `UPDATE`. Drop the old columns in a later PR, once the fallback has gone unused in
production for a while. No processing-service change.

The backfill rewrites every one of these rows once, so it carries the two size decisions
with it rather than rewriting them again later:

- Store the logits at **four bytes per class**, not eight, which halves the largest column
  in the database. Settle the `-inf` question first: if pgvector's rejection of infinity is
  a problem for masked classes, use `float4[]` and keep the halving.
- **Do not store the softmax scores at all.** They are a pure function of the logits, so
  keeping both doubles the cost of that column to save one cheap computation on read.
- **Audit the ~1,400 rows that have scores and no logits first** (309,079 against 307,663).
  Their scores cannot be recomputed from anything. Decide what happens to them before the
  column is dropped, not after.

**(c) Generic outputs table and `outputs` on the wire.** Add `AlgorithmOutputRecord`, the
type registry, and the `outputs` field on `DetectionResponse`; route by task type in
`save_results` (`ami/ml/models/pipeline.py:1076`). The field is optional, so nothing breaks
for a service that never sends it.

**(d) First measurement type.** Add `DetectionMeasurement` and one real producer, which is
what proves the routing works end to end. Needs from the processing services: a size
estimator declaring `task_type: "size_estimation"` and emitting a measurement output.

Stages (a) and (b) touch models, so each carries its own migration in the same PR.

## What we still need to verify

None of the performance claims here have been measured on the proposed design; they are
read off storage formats and off the current table. Before each stage lands:

1. **`EXPLAIN (ANALYZE)` the partial expression index.** Build one on a dimensionless
   `vector` column for a single algorithm, on a realistically sized table rather than an
   empty one, and confirm the planner matches both the cast and the `WHERE algorithm_id = N`
   predicate instead of scanning.
2. **Measure a hot classification query before and after the logits move.** Take an
   occurrence list and an occurrence detail, capture the SQL under `cachalot_disabled()`,
   and record wall time both ways on the largest local project. A claim that the move helps
   is worth nothing without the pair of numbers.
3. **Round-trip an unrecognised task type** from a processing service through `save_results`
   and confirm it lands in the generic table, that an unknown *algorithm* key still raises
   `PipelineNotConfigured`, and that neither path creates a `Classification` or changes any
   occurrence's determination.
4. **Confirm pgvector rejects nothing we send.** If `scores` or `logits` move to a `vector`
   column, check what real models emit — a `-inf` logit from a masked class would be
   rejected where a `float8[]` accepted it.
5. **Run the pgvector upgrade and confirm it on each deployment.** The decision is to be on
   0.7.0 or later, and locally that is `ALTER EXTENSION vector UPDATE;` because the image
   already carries 0.8.6 against 0.5.1 installed. What still needs checking per deployment is
   that its image offers the same, and that the update completes with the existing
   `vector(2048)` columns in place.

## Open questions

- Should `Classification` adopt the spine at all, or should the spine describe only the new
  tables? Adopting it adds a `job` column to the largest table for uniformity's sake, and
  uniformity may not be worth that.
- Where does a capture-level or occurrence-level output come from on the wire? The current
  response is detection-shaped, and an output about the whole capture has no natural home in
  it.
- Should `ClassificationResponse.features` (`ami/ml/schemas.py:136`) be deprecated once
  `embeddings` is established, and if so, on what timeline for the services still sending it?
- Does a re-run of an algorithm replace an output or append a new one? `DetectionEmbedding`
  replaces, via the unique constraint. A measurement might reasonably want history.
- Is a tag its own table or a `Classification` with a non-taxon category map? See the note
  in the catalogue; the recommendation is its own table, and it should be confirmed.
- Should an output whose `type` contradicts its algorithm's registered `task_type` warn or
  fail the batch? Failing is safer and blocks a service mid-experiment.
- `AlgorithmTaskType` is the vocabulary, so adding a kind of output means adding an enum
  value. Who agrees a new value, and does an Antenna deploy have to precede a service using
  it? The generic table softens this, since an unrecognised type is still stored.

## References

- pgvector, dimension limits, dimensionless columns and expression indexes:
  <https://github.com/pgvector/pgvector>
- `Classification`: `ami/main/models.py:3022`; `logits`/`scores`/`features_2048`:
  `ami/main/models.py:3039-3051`
- `DetectionEmbedding`: `ami/main/models.py:3429`; migration
  `ami/main/migrations/0101_detection_embedding.py`
- Vector reader, one algorithm at a time: `ami/main/models_future/embeddings.py`
- Determination logic: `Occurrence.best_prediction` `ami/main/models.py:3919`,
  `Occurrence.predictions` `ami/main/models.py:3952`
- Wire schemas: `EmbeddingResponse` `ami/ml/schemas.py:185`, `DetectionResponse`
  `ami/ml/schemas.py:204`, `ClassificationResponse` `ami/ml/schemas.py:124`
- Save path: `create_detection_embeddings` `ami/ml/models/pipeline.py:687`,
  `create_classifications` `ami/ml/models/pipeline.py:922`, `save_results`
  `ami/ml/models/pipeline.py:1076`
- `AlgorithmTaskType` and `Algorithm`: `ami/ml/models/algorithm.py:202`, `:228`
