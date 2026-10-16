# Feature vectors: how they are stored and how to query them

Feature vectors (embeddings) are stored once per detection, per model output, in one table. This
page explains the layout, the single rule every reader must follow, the queries the layout is built
for (with the function that serves each), what to avoid, and how to extend it. The code lives in
`ami/ml/models/embedding.py` (model and queryset), `ami/ml/embeddings/writer.py` (storing results)
and `ami/ml/embeddings/reader.py` (query functions). Introduced in #1462.

## Storage model

`DetectionEmbedding` has one row per (detection, algorithm):

| Column | Meaning |
|---|---|
| `detection` | The detection the vector describes. Rows cascade with it. |
| `algorithm` | The model that produced the vector. Rows cascade with it. |
| `vector` | A `halfvec` column with no declared length, stored out of line and uncompressed (`STORAGE EXTERNAL`), because vectors do not compress and this keeps heap rows small. |
| `project` | Copied from the detection's capture (or its station), so project-scoped queries need no join. |
| `job` | The job whose results stored the vector; set to null if the job is deleted. |

A vector keeps the project it was written with. Moving a station to another project does not move
its vectors: `Deployment.update_children` realigns only events, occurrences and captures. Until the
move command (#1192) or a project-consistency check (#1453) covers vectors, a moved station's vectors
stay with its old project.

Indexes: the unique constraint on (detection, algorithm), an index on
(project, algorithm, detection), an index on (algorithm, detection) that serves the writer's
length lookup (an algorithm's first row, ordered by detection), and a partial index on (job, detection)
where a job is set, for a job's list of occurrences. The foreign keys have no single-column indexes of
their own, because these already lead with them.

Because the column has no declared length, models of different lengths share the table (for example
a 2048-dimension classifier backbone and a 1024-dimension image-text model). Each algorithm
keeps one length: the writer reads the length of one existing row of the algorithm and refuses vectors
of another length with `EmbeddingDimensionMismatch`. No length is stored on `Algorithm`.

## Which algorithm a vector is stored under

A vector is stored under the algorithm the processing service names for it in the response. A
classifier that returns its own backbone features therefore stores them under that classifier's
algorithm row, while a dedicated extractor (for example BioCLIP, task type `embedding`) has its own
row. To find which models have vectors in a project, use `vector_counts_by_algorithm(project_id)`
rather than assuming an algorithm.

## A model with several outputs

A model that yields several vectors per detection in one pass (two layers, or an image vector and a
projected one) registers one algorithm per output, and the service sends one `EmbeddingResponse` per
output, each naming its own algorithm. Each output is then its own comparable set, with its own
length. A model that yields many vectors for one detection (one per image patch) is pooled to one
vector by the service first. The processing-service side of this is in `processing_services/README.md`,
"Returning feature vectors".

## The rule: one algorithm per query

Vectors from different models are not comparable. Every reader therefore takes one algorithm id,
and nothing merges models. A query that mixes
models returns noise, and it also mixes lengths, which the database rejects when distances are
computed. When a cross-model query is truly intended, say so in a comment at the call site.

## Query patterns

Each pattern names the function in `ami/ml/embeddings/reader.py` that serves it, the SQL shape,
and the index it uses. Check a plan with `EXPLAIN (ANALYZE, BUFFERS)` on realistic data before
claiming a query is cheap.

| # | Need | Function | SQL shape | Index |
|---|---|---|---|---|
| Q1 | Vectors of one model for some detections (tracking over adjacent captures, retraining on verified detections) | `vectors_for_detections(ids, algorithm_id)` | `detection_id = ANY(..) AND algorithm_id = A` | unique (detection, algorithm) for a few captures' worth; for thousands of ids the planner may prefer (algorithm, detection) or a sequential scan, measured at 17-19 ms for 5,000 ids on a 450k-row table (a sequential scan; 12 ms when forced onto the algorithm index; measured while the table also had a `key` column) |
| Q2 | Occurrences sorted by similarity to one occurrence | not in this PR: the sort ships in its own follow-up pull request | per occurrence, a representative detection's vector, then cosine distance | (algorithm, detection), probed once per occurrence; an exact scan |
| Q3 | All of one model's vectors in a project (exports, clustering) | `project_vectors(project_id, algorithm_id, detection_ids=None, chunk_size=2000)` | `project_id = P AND algorithm_id = A AND detection_id > last ORDER BY detection_id LIMIT n` | (project, algorithm, detection): rows come out in order, so no sort |
| Q4 | Which models have vectors in a project, and how many | `vector_counts_by_algorithm(project_id)` | `GROUP BY algorithm_id` within a project | the same index (index-only); when one project holds most of the table the planner may scan the table instead, measured at 36 ms for 359k rows |
| Q5 | Detections that still lack a vector from a model | `detections_missing_vectors(detections, algorithm_id)` | `NOT EXISTS` on (detection, algorithm) added to the caller's queryset | (algorithm, detection), index-only |
| Q6 | Nearest neighbours of one vector, when exact scans are too slow | not shipped | `ORDER BY vector::halfvec(D) <=> seed` within one algorithm | a partial HNSW index per algorithm, see below |
| Q7 | Which algorithms stored vectors in a project (choices for the occurrence algorithm filter) | `Algorithm.objects.used_in_project(project)` | `SELECT DISTINCT algorithm_id WHERE project_id = P`, next to its detection and classification lookups | reads one project's range of (project, algorithm, detection); not measured |
| Q8 | Which algorithms have a vector for one occurrence (`embedding_algorithms` on the occurrence detail) | `OccurrenceSerializer.get_embedding_algorithms` | `EXISTS` per algorithm on the occurrence's detections, one query | (algorithm, detection) probed through the detection's occurrence; not measured |
| Q9 | Occurrences with a vector from given algorithms (the `algorithm` and `not_algorithm` filters) | `OccurrenceQuerySet.processed_by_algorithm()` | `build_processed_by_algorithm_q()` in `ami/main/models_future/filters.py`: the vector `EXISTS` is ORed in only when the algorithms have vectors | (algorithm, detection); not measured |

`project_vectors` pages with `detection_id > last` rather than `OFFSET`, so every page costs the
same and memory stays at one chunk. Callers keep their own scope by passing `detection_ids` or by
filtering the queryset given to `detections_missing_vectors`.

## Anti-patterns

- **Computing similarity in Python over unbounded rows.** Use the database's distance operators,
  or the chunked reader for exports. Never `list()` a project's vectors.
- **Mixing models.** Always filter by algorithm; a missing filter is a silent correctness bug.
- **`.distinct()` or JSON round trips over vector rows.** De-duplicating sorts the vector column
  and is very slow; the unique constraint already prevents duplicates.
- **Omitting the project filter** on project-scoped reads. The index leads with `project`, and the
  filter also enforces visibility.
- **Reading an algorithm's rows by algorithm alone** at scale. Only the (algorithm, detection)
  index leads with that column; it is meant for the writer's one-row length lookup, and a scan of
  all of an algorithm's rows still reads the table.

## Logits are not vectors to search

Per-class logits belong to a classification, not to this table. Measured on a copy of production
data: 308 thousand classifications carry logits, taking about 4.3 GB of out-of-line storage; one
classifier has 29,176 classes, which is above pgvector's 16,000-dimension storage limit; and
37,776 (detection, algorithm) groups hold several classifications that disagree, so logits must
stay tied to their own classification row. Keep them on `Classification` and defer them in list
queries. If they move, use a side table keyed by classification with a `real[]` or bytea column
stored out of line, or files in object storage for bulk training exports; do not put them here.
Store only the top-k when the full vector is not needed. For all but one small model the stored
scores equal the softmax of the logits, so they can be derived.

## Reduced dimensions

A reduction (PCA, UMAP, random projection) of a vector is a different model output. Give it its own
`Algorithm` row, recording the method, the parent algorithm and the fit parameters, and store its
vectors in this table under that algorithm id. Its length and any index are then its own. Two
dimensional layouts for display are derived data that can be recomputed; store them only if a page
needs them persistently.

## Adding a sibling table

Capture-level or taxon-level vectors get sibling tables of the same shape (`SourceImageEmbedding`,
`TaxonEmbedding`), not a polymorphic target column on this table. That keeps foreign keys,
cascades and indexes exact. Only `DetectionEmbedding` exists today; the shared parts live in
`ami/ml/models/embedding.py` so a sibling is a small change:

1. Subclass `BaseEmbedding` (algorithm, job, project, vector, timestamp, and `save()` that
   fills the project). Add the target foreign key with `db_index=False`, and implement the
   `fill_project_ids(embeddings)` classmethod (how a vector finds its project from its target).
2. Subclass `BaseEmbeddingQuerySet` with `target_field = "<target>"` and use it as the manager.
   `store()`, `stored_length()` and `for_algorithm()` then work unchanged. The base foreign keys use
   `related_name="%(class)ss"`. `DetectionEmbedding` declares its own related names
   (`detection_embeddings`, `embeddings`); new sibling tables use the base's `%(class)ss` names.
3. Write the Meta by hand: a unique constraint on (target, algorithm),
   an index on (project, algorithm, target), an index on (algorithm, target) for the
   writer's length lookup, and the partial (job, target) index. Give the indexes explicit short names
   (the 30 character limit) like `ml_detemb_*`.
4. The migration must repeat what `makemigrations` does not infer: create the table, then run
   `ALTER TABLE <table> ALTER COLUMN vector SET STORAGE EXTERNAL`, as `ml/0031` does for detections.
   Enabling pgvector is already done by `ml/0030`.
5. Add reader and writer functions next to the detection ones, keyed by algorithm like
   every other reader. The writer stays specific to its target (matching responses to targets is
   not shared).

Open question: taxa are not project-scoped, so a `TaxonEmbedding` might carry a nullable `project`
or none at all. The base requires a project, so that table would override the field, or the base
would need to be relaxed first. Decide this before building it.

## Nearest-neighbour indexes (HNSW)

Exact scans were measured at about 16 to 19 ms per 1,000 candidate rows, which is fine for a
filtered list. When that stops being enough, add a partial HNSW index per algorithm on the
cast expression, for example
`CREATE INDEX ... USING hnsw ((vector::halfvec(1024)) halfvec_cosine_ops) WHERE algorithm_id = A`.
The cast is valid because each algorithm has one length, and halfvec HNSW supports up to 4,000
dimensions. Measured costs at about 350 thousand rows: 0.9 to 2.7 GB and 3.5 to 15 minutes to
build per model, with recall between 0.68 and 0.98, so results are approximate and filtered
queries need care. Not created by default.

## Precision

`halfvec` stores 16-bit floats. On 600 real 2,048-dimension vectors the cosine similarity changed
by at most 1.5e-4 and the top-1 neighbour agreed in 98.2 percent of cases. Values outside the
half-precision range (beyond 65,504, NaN, infinity) cannot be stored; the writer skips them with a
warning. Keep full precision somewhere else only where that difference matters, and say so.

## Query cache

The vector table is listed in `CACHALOT_UNCACHABLE_TABLES` (`config/settings/base.py`), so queries
that read it are never cached: vector rows are large, and the cache shares Redis with async job
state. This only works when django-cachalot can see the table in the query. It does not see tables
inside a negated `Exists` in `filter()`, which is why `detections_missing_vectors` uses `exclude()`.

## Deletion and retention

Vectors are deleted with their detection or algorithm. Deleting a job keeps its vectors (the job
reference becomes null). Saving identical results twice changes nothing; a new vector for the same
(detection, algorithm) replaces the old one in place, and the replacing job is recorded on
the row, so a job that changed a vector is found by the "created or updated by job" filter. A vector
that is identical on a re-run is not written, and keeps the job that first stored it.
