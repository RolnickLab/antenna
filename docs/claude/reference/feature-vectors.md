# Feature vectors: how they are stored and how to read them

Feature vectors (embeddings) are stored once per detection and algorithm, in one table. This page
covers the layout, the rules for writing and reading, the reads the layout is built for (with
measured plans), and how to add a vector table for another target. The code is
`ami/ml/models/embedding.py` (models) and `ami/ml/embeddings/writer.py` (storing results).
Introduced in #1462; design and goals in #1457.

## Storage model

`DetectionEmbedding` has one row per (detection, algorithm):

| Column | Meaning |
|---|---|
| `detection` | The detection the vector describes. Rows cascade with it. |
| `algorithm` | The algorithm that produced the vector (one per ML model output). Rows cascade with it. |
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

Vectors from different algorithms are not comparable, so every read is for one algorithm, and each
algorithm stores at most one vector per detection. An ML model with several outputs (two layers, or an
image vector and a projected one) registers one algorithm per output; see `processing_services/README.md`,
"Returning feature vectors". A reduction of a vector (PCA, UMAP) is also its own algorithm.

Each algorithm has one vector length, `Algorithm.embedding_dimensions`, declared by its processing
service in `/info` and recorded at registration. An unsized column lets algorithms of different lengths
share the table, and the declared length keeps one algorithm's vectors comparable. If a service later
declares a different length for an algorithm that already has one, registration keeps the registered
length and logs a warning, and vectors of the new length are refused when results are saved: register
the new ML model under a new algorithm key. Do not delete the old algorithm to make room: its
classifications and detections would lose their algorithm.

## Writing

`save_results` runs `validate_detection_embeddings` before it saves anything, then
`create_detection_embeddings` after the detections are saved. The results are refused, with nothing
written, when a vector:

- comes from an algorithm the pipeline did not register (`PipelineNotConfigured`),
- or (`EmbeddingRefused`) comes from an algorithm that declares no length, has another length, holds a
  value half precision cannot store (NaN, infinity, beyond ±65,504), repeats an algorithm on one
  detection, sits on a detection without a bounding box, or belongs to a capture without a project.

A refusal fails the job, on both paths: it means the pipeline's registration and the processing service
disagree, and every retry would fail the same way. In the async path `process_nats_pipeline_result`
(`ami/jobs/tasks.py`) acks the message and fails the job rather than letting NATS redeliver it. Fix the
service or its registration, or run the job with a pipeline that has no embedding algorithm.

The first vector stored for a (detection, algorithm) is kept: later ones are not written
(`INSERT … ON CONFLICT DO NOTHING`). To store new vectors, delete the detections or register the new ML
model as a new algorithm.

## Filling in missing vectors

There is no separate embedding pipeline. Any pipeline algorithm that declares a vector length
(`Algorithm.writes_embeddings`, whatever its task type: a species classifier can also return its
backbone's vectors) is treated like a classifier by `filter_processed_images`: a capture is processed again
while one of its real detections lacks a vector from that algorithm. The detections are matched to the
existing ones and the writer adds only the missing vectors. A declared length is therefore a promise to
send a vector for every detection on every request; a service that declares one and sends none makes its
captures reprocess on every job.

A fill-in runs the whole pipeline again, and two costs follow (measured in the async end-to-end run on
#1462). Classifiers run again, and their scores vary by about 0.00005 between GPU runs, so the exact-score
duplicate check stores a repeat classification for most detections. Detector boxes can also move by one
pixel, so exact-box matching saves a near-duplicate detection, and the original stays without a vector until
a later job reproduces its box.

Concurrent writers: the writer takes no lock of its own. Its one `bulk_create` runs its INSERTs of up to
200 rows in a single transaction, so the inserted rows stay locked until the last INSERT finishes. Rows
are inserted in (detection, algorithm) order, because two writers that insert shared rows in different
orders deadlock; with the ordering removed, `TestConcurrentWriters` fails with "deadlock detected"
(checked on 2026-10-16).

## Reading

Every read filters by one algorithm (`for_algorithm`), and project-scoped reads also filter by
project first, which enforces visibility as well. Check a plan with `EXPLAIN (ANALYZE, BUFFERS)` on
realistic data before calling a query cheap. `TestReadingVectors` shows the basic read to copy.

| Need | SQL shape | Index and measured cost |
|---|---|---|
| One algorithm's vectors for some detections (tracking over adjacent captures, retraining sets) | `detection_id = ANY(..) AND algorithm_id = A` | unique (detection, algorithm) for a few captures' worth; 17-19 ms for 5,000 ids on a 450k-row table, where the planner chose a sequential scan (12 ms forced onto the algorithm index) |
| All of one algorithm's vectors in a project (exports, clustering) | `project_id = P AND algorithm_id = A AND detection_id > last ORDER BY detection_id LIMIT n`, paged by the last id rather than `OFFSET` | (project, algorithm, detection): rows come out in order, with no sort |
| Which algorithms have vectors in a project, and how many (`vector_counts_by_algorithm`; `algorithm_with_most_vectors` picks the similarity sort's default model) | `GROUP BY algorithm_id` within a project | the same index, index-only; 36 ms for 359k rows, when the planner scanned the table because one project held most of it |
| Detections still lacking a vector from an algorithm | `NOT EXISTS` on (detection, algorithm), added to the caller's detection queryset | (algorithm, detection), index-only; 138 ms over a 179k-detection project (parallel hash anti-join) |
| Occurrences ordered by similarity to one occurrence (`OccurrenceQuerySet.with_visual_similarity()`, through `representative_embeddings()` in `ami/ml/embeddings/reader.py`) | the representative detection's vector per occurrence, then cosine distance; the seed (`similar_to`) is required and lists above `SIMILARITY_SORT_MAX_OCCURRENCES` are refused | (algorithm, detection), probed once per occurrence; exact scans measured at 16-19 ms per 1,000 candidates |
| Which algorithms stored vectors in a project (choices for the occurrence algorithm filter) | `SELECT DISTINCT algorithm_id WHERE project_id = P` in `Algorithm.objects.used_in_project(project)`, next to its detection and classification lookups | one project's range of (project, algorithm, detection); not measured |
| Which algorithms have a vector for one occurrence (`embedding_algorithms` on the occurrence detail, `OccurrenceSerializer.get_embedding_algorithms`) | `EXISTS` per algorithm on the occurrence's detections, one query | (algorithm, detection) probed through the detection's occurrence; not measured |
| Occurrences with a vector from given algorithms (the `algorithm` and `not_algorithm` filters, `OccurrenceQuerySet.processed_by_algorithm()`) | `build_processed_by_algorithm_q()` in `ami/main/models_future/filters.py` ORs in the vector `EXISTS` only when the algorithms have vectors | (algorithm, detection); not measured |

Measured on a copy of production data in October 2026, on an earlier version of this table. Nearest-neighbour (HNSW) indexes are not created; #1500 tracks when to add them.

Avoid: computing similarity in Python over unbounded rows (use the database's distance operators,
or read in pages); a read without an algorithm filter, which silently mixes algorithms; and `.distinct()`
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

1. Subclass `BaseEmbedding` (algorithm, job, project, vector) and add the target foreign
   key with `db_index=False`.
2. Use a `BaseEmbeddingQuerySet` subclass as the manager.
3. In the Meta, set `indexes, constraints = embedding_table_options("<target>", prefix=..., short_target=...)`:
   a unique constraint on (target, algorithm) and indexes on (project, algorithm, target), (algorithm,
   target) and a partial (job, target). The reverse names come from the base (`algorithm.<table>s`).
4. In the migration, after creating the table, run
   `ALTER TABLE <table> ALTER COLUMN vector SET STORAGE EXTERNAL`, as `ml/0031` does.
5. Write a writer for the target next to the detection one, and add the table to
   `CACHALOT_UNCACHABLE_TABLES`.

Taxa belong to no project, so a `TaxonEmbedding` needs a decision first: the project the vector was
computed for, or a nullable project, which means overriding the base field.
