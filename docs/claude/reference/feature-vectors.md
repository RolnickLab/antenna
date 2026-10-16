# Feature vectors: how they are stored and how to read them

Feature vectors (embeddings) are stored once per detection and model output, in one table. This page
covers the layout, the rules for writing and reading, the reads the layout is built for (with
measured plans), and how to add a vector table for another target. The code is
`ami/ml/models/embedding.py` (models) and `ami/ml/embeddings/writer.py` (storing results).
Introduced in #1462; design and goals in #1457.

## Storage model

`DetectionEmbedding` has one row per (detection, algorithm):

| Column | Meaning |
|---|---|
| `detection` | The detection the vector describes. Rows cascade with it. |
| `algorithm` | The model output that produced the vector. Rows cascade with it. |
| `vector` | A `halfvec` column with no declared length, stored out of line and uncompressed (`STORAGE EXTERNAL`), because vectors do not compress and this keeps heap rows small. |
| `project` | The project of the detection's capture, so project-scoped queries need no join. |
| `job` | The job whose results stored the vector; set to null if the job is deleted. |

Indexes: the unique constraint on (detection, algorithm); (project, algorithm, detection);
(algorithm, detection), which also serves deleting an algorithm with its vectors; and a partial
(job, detection) index where a job is set, which also serves clearing the job when it is deleted.
The foreign keys have no single-column indexes, because these lead with them.

A vector keeps the project it was written with. Moving a station to another project does not move
its vectors (`Deployment.update_children` realigns events, occurrences and captures only); the move
command (#1192) or a project-consistency check (#1453) is where that belongs.

## One algorithm, one length

Vectors from different models are not comparable, so every read is for one algorithm, and each
algorithm stores at most one vector per detection. A model with several outputs (two layers, or an
image vector and a projected one) registers one algorithm per output; see `processing_services/README.md`,
"Returning feature vectors". A reduction of a vector (PCA, UMAP) is also its own algorithm.

Each algorithm has one vector length, `Algorithm.embedding_dimensions`, declared by its processing
service in `/info` and recorded at registration. An unsized column lets models of different lengths
share the table, and the declared length keeps one model's vectors comparable. Registration refuses
a different length for an algorithm that already has one: register the new model under a new
algorithm key, or delete the algorithm (and with it its vectors) first.

## Writing

`save_results` runs `validate_detection_embeddings` before it saves anything, then
`create_detection_embeddings` after the detections are saved. A batch is refused, with nothing
written, when a vector:

- comes from an algorithm the pipeline did not register (`PipelineNotConfigured`),
- comes from an algorithm that declares no length, or has another length (`EmbeddingDimensionMismatch`),
- holds a value half precision cannot store (NaN, infinity, beyond ±65,504), or a detection carries
  two vectors from one algorithm (both rejected by the results schema, so the async results endpoint
  answers 400 before anything is queued).

The first vector stored for a (detection, algorithm) is kept: later ones are not written
(`INSERT … ON CONFLICT DO NOTHING`), as detections and classifications are never overwritten either. To
store new vectors, delete the detections or register the new model as a new algorithm.

Concurrent writers: the writer opens no transaction and takes no lock of its own. Each INSERT of up
to 200 rows locks its rows for that statement only. Rows are inserted in (detection, algorithm)
order, because two inserts that share rows in different orders deadlock; `TestConcurrentWriters`
reproduces the deadlock without the ordering.

## Reading

Every read filters by one algorithm (`for_algorithm`), and project-scoped reads also filter by
project first, which enforces visibility as well. Check a plan with `EXPLAIN (ANALYZE, BUFFERS)` on
realistic data before calling a query cheap. `TestReadingVectors` shows the basic read to copy.

| Need | SQL shape | Index and measured cost |
|---|---|---|
| One model's vectors for some detections (tracking over adjacent captures, retraining sets) | `detection_id = ANY(..) AND algorithm_id = A` | unique (detection, algorithm) for a few captures' worth; 17-19 ms for 5,000 ids on a 450k-row table, where the planner chose a sequential scan (12 ms forced onto the algorithm index) |
| All of one model's vectors in a project (exports, clustering) | `project_id = P AND algorithm_id = A AND detection_id > last ORDER BY detection_id LIMIT n`, paged by the last id rather than `OFFSET` | (project, algorithm, detection): rows come out in order, with no sort |
| Which models have vectors in a project, and how many | `GROUP BY algorithm_id` within a project | the same index, index-only; 36 ms for 359k rows, when the planner scanned the table because one project held most of it |
| Detections still lacking a vector from a model | `NOT EXISTS` on (detection, algorithm), added to the caller's detection queryset | (algorithm, detection), index-only; 138 ms over a 179k-detection project (parallel hash anti-join) |
| Occurrences ordered by similarity to one occurrence | a representative detection's vector per occurrence, then cosine distance | (algorithm, detection), probed once per occurrence; exact scans measured at 16-19 ms per 1,000 candidates |

Measured on a copy of production data in October 2026, partly while the table had a since-removed
`key` column. Nearest-neighbour (HNSW) indexes are not created; #1500 tracks when to add them.

Avoid: computing similarity in Python over unbounded rows (use the database's distance operators,
or read in pages); a read without an algorithm filter, which silently mixes models; and `.distinct()`
over vector rows, which sorts the vector column and is very slow (the unique constraint already
prevents duplicates).

## Precision

`halfvec` stores 16-bit floats. On 600 real 2,048-dimension vectors, cosine similarity changed by at
most 1.5e-4 and the top-1 neighbour agreed in 98.2 percent of cases.

## Query cache

The vector table is listed in `CACHALOT_UNCACHABLE_TABLES` (`config/settings/base.py`): vector rows
are large, and the cache shares Redis with async job state. django-cachalot only honours this when
it can see the table in the query, and it does not see tables inside a negated `Exists` passed to
`filter()`. Write such a query with `exclude(Exists(...))`.

## Adding a vector table for another target

Capture and taxon vectors get their own tables of the same shape, not a polymorphic target column
on this one, so foreign keys, cascades and indexes stay exact. `ami/ml/models/embedding.py` has
commented-out `SourceImageEmbedding` and `TaxonEmbedding` to start from:

1. Subclass `BaseEmbedding` (algorithm, job, project, vector, timestamp) and add the target foreign
   key with `db_index=False`.
2. Use a `BaseEmbeddingQuerySet` subclass as the manager.
3. Write the Meta: a unique constraint on (target, algorithm), and indexes on (project, algorithm,
   target), (algorithm, target) and a partial (job, target), with explicit names under 30 characters.
4. In the migration, after creating the table, run
   `ALTER TABLE <table> ALTER COLUMN vector SET STORAGE EXTERNAL`, as `ml/0031` does.
5. Write a writer for the target next to the detection one, and add the table to
   `CACHALOT_UNCACHABLE_TABLES`.

Taxa belong to no project, so a `TaxonEmbedding` needs a decision first: the project the vector was
computed for, or a nullable project, which means overriding the base field.
