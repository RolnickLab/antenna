# Storing wide float arrays in PostgreSQL 16: pgvector types, real[], TOAST and alternatives

**Question.** A platform must store, in one table family, per-detection float arrays of many
kinds: embeddings from several models (1,024-d and 2,048-d, millions of rows over time), raw
classifier logits (2,497 wide for ~90k rows, 29,176 wide for ~8k rows), and softmax scores.
Today they are `float8[]` on the classification row: 4.3 GB of TOAST against a 118 MB heap.
Readers pull arrays into numpy in bulk; no similarity search runs in SQL yet. What are the
storage options, limits and trade-offs?

**Produced by.** A research agent (Claude Sonnet), 2026-09-29, supervised. Sources are the
pgvector README, PostgreSQL docs and vendor or blog posts, marked where vendor-flavoured.

## 1. pgvector types and limits

Source: https://github.com/pgvector/pgvector

| Type | Storage | Max dims (storage) | Max dims (HNSW / IVFFlat index) |
|---|---|---|---|
| `vector` | 4·d + 8 bytes | 16,000 | 2,000 |
| `halfvec` | 2·d + 8 bytes | 16,000 | 4,000 |
| `bit` | d/8 + 8 bytes | not stated | 64,000 |
| `sparsevec` | 8·nnz + 16 bytes | 16,000 non-zeros | 1,000 non-zeros (HNSW) |

- All elements must be finite: NaN, Infinity and -Infinity are rejected.
- Mixed dimensions in one column: an unsized `vector` column plus a partial expression index per
  model: `CREATE INDEX ON embeddings USING hnsw ((embedding::vector(3)) vector_l2_ops) WHERE
  (model_id = 123)`. Queries must repeat the same cast and `WHERE`.
- Arrays: for `double precision[]` or `real[]` storage the README suggests a
  `vector_dims(embedding::vector) = N` CHECK and an expression index on the cast, so an array can
  stay the storage type and be cast only where an index needs it.
- Filtered ANN: iterative scans (`hnsw.iterative_scan`, `strict_order` or `relaxed_order`) help
  when a filter leaves few results (0.8.0+).
- Build speed: the graph should fit in `maintenance_work_mem`; parallel workers via
  `max_parallel_maintenance_workers`.

## 2. real[] versus pgvector types, and TOAST

- Arrays are variable-length; default strategy `EXTENDED` compresses first, then moves out of
  line above ~2 KB. https://www.postgresql.org/docs/16/storage-toast.html
- Lossless compression of float32 embeddings reaches only about 1.2x because mantissa bits are
  near maximum entropy (a paper's claim, not a Postgres measurement).
  https://arxiv.org/html/2602.00079v4
- A search result claiming float arrays never compress described scalar floats, not arrays, and
  was discarded. An LZ4 vs pglz table-size comparison (38 / 41 / 98 GB) was probably not
  embeddings and could not be sourced. https://www.tigerdata.com/blog/optimizing-postgresql-performance-compression-pglz-vs-lz4
- Practical consequence: compression buys little on float arrays and costs CPU on every read;
  `ALTER TABLE ... ALTER COLUMN ... SET STORAGE EXTERNAL` skips it.
- Keep wide arrays off hot rows: a separate table joined by primary key. One measurement:
  updating 20,000 rows of 768-d vectors doubled the TOAST table from 81 MB to 159 MB and vacuum
  did not return the space. https://dev.to/googleai/embedding-versions-management-toast-and-bloating-in-postgresql-2g2k
- The measured 4.3 GB TOAST against a 118 MB heap matches the docs: the main table stays small
  and wide values live out of line.

## 3. Alternatives

- pgvectorscale (Rust, PostgreSQL licence): StreamingDiskANN with statistical binary
  quantization; claims 28x lower p95 than Pinecone on 50M 768-d vectors; documents no maximum
  dimension and no `halfvec` support. https://github.com/timescale/pgvectorscale
- Lantern: separate extension with its own HNSW index; maintenance status not found; the
  available benchmark is vendor-adjacent. https://tembo.io/blog/postgres-vector-search-pgvector-and-lantern
- pg_embedding: discontinued; Neon directed users to pgvector.
- External stores (Qdrant, Milvus, Weaviate, LanceDB): faster pure vector search; a second
  system to keep in sync with detection rows. https://zilliz.com/comparison/qdrant-vs-pgvector
  (vendor comparison)
- Files in object storage (Parquet, NPZ): no source found; fits bulk read by model, gives no
  SQL joins or ANN.

## 4. Schema patterns

- One table with an unsized vector column `(model_id, item_id, embedding)` and one partial
  expression HNSW index per model or width (pgvector README; https://github.com/Aquilo-Solution-S/Proxima/pull/329).
- Alternative: one fixed-width column per model plus a `model_version` column.
  https://dbadataverse.com/tech/postgresql/2026/05/pgvector-gotchas-dimension-mismatch-casting-errors-and-alter-table-solved-2026
- JSONB for vectors: no benchmark found; the agent's reasoning is that floats become numeric
  text, cannot be cast cheaply, and cannot be ANN-indexed.
- Logits or top-k in Postgres: no published pattern found.

## 5. Published numbers

- Bytes per dimension: `vector` 4·d + 8, `halfvec` 2·d + 8, `bit` d/8 + 8 (pgvector README).
- HNSW index roughly 1.5 to 2x the raw data (estimate).
  https://neon.com/blog/pgvector-30x-faster-index-build-for-your-vector-embeddings
  The dev.to post above measured a 78 MB index for 20,000 768-d rows.
- Build, 1M x 1536-d, m=16, ef_construction=200: about 87 min single-threaded, about 9.5 min
  with parallel builds. https://supabase.com/blog/pgvector-fast-builds
- 10M x 1536-d on a 64 vCPU, 512 GB machine (Neon link); 50M rows reported at 2 to 6 hours.
  https://www.instaclustr.com/education/vector-database/pgvector-performance-benchmark-results-and-5-ways-to-boost-performance/
- pgvectorscale: 21 MB index vs 193 MB HNSW on unspecified data (vendor figure).

## What this means for the design

1. One side table keyed by (item, model, kind) with a dimension recorded, off the
   classification row.
2. `real[]` (float4) halves `float8[]` and has no 16,000-dimension cap, if logits stay in
   Postgres.
3. `SET STORAGE EXTERNAL` on the array column: float32 compresses about 1.2x at best.
4. 29,176-wide logits exceed every pgvector index cap; keep them unindexed, or store top-k
   indices and scores separately if sparse access is needed.
5. Add ANN later with a partial expression HNSW index per model; cast 2,048-d to `halfvec`
   (HNSW cap 4,000 vs 2,000 for `vector`); 1,024-d can use `vector`.
6. A per-model dims CHECK, and reject non-finite values on write, since pgvector casts reject
   them.
7. Budget index builds: raise `maintenance_work_mem` and parallel workers; minutes at 1M rows,
   hours at tens of millions.
8. Skip a separate vector store for now.

## Could not verify

The real compression ratio of Postgres float arrays (no Postgres-specific measurement); the
origin and data type of the 38 / 41 / 98 GB comparison; pgvectorscale's maximum dimension and
`halfvec` support; Lantern's current status; any Postgres pattern for wide logits; JSONB being
measurably worse for vectors.
