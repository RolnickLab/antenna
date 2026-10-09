# Feature vectors: how they are stored and how to query them

Feature vectors (embeddings) are stored once per detection, per model output, in one table. This
page explains the layout, the single rule every reader must follow, the queries the layout is built
for (with the function that serves each), what to avoid, and how to extend it. The code lives in
`ami/ml/models/embedding.py` (model and queryset), `ami/ml/embeddings/writer.py` (storing results)
and `ami/ml/embeddings/reader.py` (query functions). Introduced in #1462.

## Storage model

`DetectionEmbedding` has one row per (detection, algorithm, key):

| Column | Meaning |
|---|---|
| `detection` | The detection the vector describes. Rows cascade with it. |
| `algorithm` | The model that produced the vector. Rows cascade with it. |
| `key` | The name of the output when one model returns several (default `embedding`). |
| `vector` | A `halfvec` column with no declared length, stored out of line and uncompressed (`STORAGE EXTERNAL`), because vectors do not compress and this keeps heap rows small. |
| `project` | Copied from the detection's capture (or its station), so project-scoped queries need no join. |
| `job` | The job whose results stored the vector; set to null if the job is deleted. |

Indexes: the unique constraint on (detection, algorithm, key), an index on
(project, algorithm, key, detection), an index on (algorithm, key, detection) that serves the writer's
length lookup (the first row of a pair, ordered by detection), and a partial index on (job, detection)
where a job is set, for a job's list of occurrences. The foreign keys have no single-column indexes of
their own, because these already lead with them.

Because the column has no declared length, models of different lengths share the table (for example
a 2048-dimension classifier backbone and a 1024-dimension image-text model). Each (algorithm, key)
keeps one length: the writer reads the length of one existing row of the pair and refuses vectors
of another length with `EmbeddingDimensionMismatch`. No length is stored on `Algorithm`.

## Which algorithm a vector is stored under

A vector is stored under the algorithm the processing service names for it in the response. A
classifier that returns its own backbone features therefore stores them under that classifier's
algorithm row, while a dedicated extractor (for example BioCLIP, task type `embedding`) has its own
row. To find which models have vectors in a project, use `vector_counts_by_algorithm(project_id)`
rather than assuming an algorithm.

## The rule: one (algorithm, key) per query

Vectors from different models, or from different keys of one model, are not comparable. Every
reader therefore takes an algorithm id and a key, and nothing merges pairs. A query that mixes
pairs returns noise, and it also mixes lengths, which the database rejects when distances are
computed. When a cross-model query is truly intended, say so in a comment at the call site.

## Query patterns

Each pattern names the function in `ami/ml/embeddings/reader.py` that serves it, the SQL shape,
and the index it uses. Check a plan with `EXPLAIN (ANALYZE, BUFFERS)` on realistic data before
claiming a query is cheap.

| # | Need | Function | SQL shape | Index |
|---|---|---|---|---|
| Q1 | Vectors of one model for some detections (tracking over adjacent captures, retraining on verified detections) | `vectors_for_detections(ids, algorithm_id, key)` | `detection_id = ANY(..) AND algorithm_id = A AND key = K` | unique (detection, algorithm, key) for a few captures' worth; for thousands of ids the planner may prefer (algorithm, key, detection) or a sequential scan, measured at 17-19 ms for 5,000 ids on a 450k-row table (a sequential scan; 12 ms when forced onto (algorithm, key, detection)) |
| Q2 | Occurrences sorted by similarity to one occurrence | not in this PR: the sort ships in its own follow-up pull request | per occurrence, a representative detection's vector, then cosine distance | (algorithm, key, detection), probed once per occurrence; an exact scan |
| Q3 | All of one model's vectors in a project (exports, clustering) | `project_vectors(project_id, algorithm_id, key, detection_ids=None, chunk_size=2000)` | `project_id = P AND algorithm_id = A AND key = K AND detection_id > last ORDER BY detection_id LIMIT n` | (project, algorithm, key, detection): rows come out in order, so no sort |
| Q4 | Which models have vectors in a project, and how many | `vector_counts_by_algorithm(project_id, key=None)` | `GROUP BY algorithm_id, key` within a project | the same index (index-only); when one project holds most of the table the planner may scan the table instead, measured at 36 ms for 359k rows |
| Q5 | Detections that still lack a vector from a model | `detections_missing_vectors(detections, algorithm_id, key)` | `NOT EXISTS` on (detection, algorithm, key) added to the caller's queryset | (algorithm, key, detection), index-only |
| Q6 | Nearest neighbours of one vector, when exact scans are too slow | not shipped | `ORDER BY vector::halfvec(D) <=> seed` within one (algorithm, key) | a partial HNSW index per (algorithm, key), see below |

`project_vectors` pages with `detection_id > last` rather than `OFFSET`, so every page costs the
same and memory stays at one chunk. Callers keep their own scope by passing `detection_ids` or by
filtering the queryset given to `detections_missing_vectors`.

## Anti-patterns

- **Computing similarity in Python over unbounded rows.** Use the database's distance operators,
  or the chunked reader for exports. Never `list()` a project's vectors.
- **Mixing models.** Always filter by algorithm and key; a missing filter is a silent correctness bug.
- **`.distinct()` or JSON round trips over vector rows.** De-duplicating sorts the vector column
  and is very slow; the unique constraint already prevents duplicates.
- **Omitting the project filter** on project-scoped reads. The index leads with `project`, and the
  filter also enforces visibility.
- **Reading a pair's rows by (algorithm, key) alone** at scale. Only the (algorithm, key, detection)
  index leads with those columns; it is meant for the writer's one-row length lookup, and a scan of
  all of a pair's rows still reads the table.

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

## Vectors for other things

Capture-level or taxon-level vectors should get sibling tables of the same shape (for example
`SourceImageEmbedding`, `TaxonEmbedding`), not a polymorphic target column on this table. That
keeps foreign keys, cascades and indexes exact.

## Nearest-neighbour indexes (HNSW)

Exact scans were measured at about 16 to 19 ms per 1,000 candidate rows, which is fine for a
filtered list. When that stops being enough, add a partial HNSW index per (algorithm, key) on the
cast expression, for example
`CREATE INDEX ... USING hnsw ((vector::halfvec(1024)) halfvec_cosine_ops) WHERE algorithm_id = A AND key = 'embedding'`.
The cast is valid because each pair has one length, and halfvec HNSW supports up to 4,000
dimensions. Measured costs at about 350 thousand rows: 0.9 to 2.7 GB and 3.5 to 15 minutes to
build per model, with recall between 0.68 and 0.98, so results are approximate and filtered
queries need care. Not created by default.

## Precision

`halfvec` stores 16-bit floats. On 600 real 2,048-dimension vectors the cosine similarity changed
by at most 1.5e-4 and the top-1 neighbour agreed in 98.2 percent of cases. Values outside the
half-precision range (beyond 65,504, NaN, infinity) cannot be stored; the writer skips them with a
warning. Keep full precision somewhere else only where that difference matters, and say so.

## Deletion and retention

Vectors are deleted with their detection or algorithm. Deleting a job keeps its vectors (the job
reference becomes null). Saving identical results twice changes nothing; a new vector for the same
(detection, algorithm, key) replaces the old one in place.
