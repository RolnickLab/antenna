# Vector database data models: several vectors per entity, model identity, filtering, tenancy

**Question.** The planned Postgres design stores one row per `(target, algorithm, key, vector)`
with a partial HNSW index per `(algorithm, key)`. How do dedicated vector databases model the
same problem: several vectors per entity, the producing model, payload and filtered search,
multi-tenancy, quantization, and where pgvector stops being enough?

**Produced by.** A research agent (Claude Sonnet), 2026-10-01, supervised. Primary docs fetched
where available; four pages 404'd and are listed at the end. Benchmarks are vendor or blog
numbers unless stated.

**Verdict.** The plan matches how dedicated systems work. Model identity lives on the vector
field or collection, never inside the row's payload. Tenancy is a filterable key with
co-location. Quantization is a per-index setting. Vector DBs are secondary stores.

## Comparison

| System | Multiple vectors per entity | Model identity | Filtering | Tenancy | Quantization |
|---|---|---|---|---|---|
| Qdrant | Named vectors per point, each with its own size and distance; named vectors can be added or removed on a live collection | The vector's name (our "algorithm/key"); inference config can carry a model string | Payload indexes, filter during HNSW traversal | Payload partition: keyword index with `is_tenant=true` co-locates a tenant; custom shards for few big tenants | float16, uint8; scalar (4x), binary (32x), product (64x), 4-bit |
| Milvus | Multiple vector fields per collection (default cap low, raisable to 10 via `proxy.maxVectorFieldNum`); hybrid search with RRF or weighted rerank | Field name | Scalar fields in a filter expression | Database / collection / partition / partition key (hash into 16 default partitions; per-key index isolation, HNSW only) | Index-level options |
| Weaviate | Named vectors per object; new ones can be added after creation | Per-vector config incl. vectorizer; changing vectorizer or index type needs a new collection | Inverted index per property | Each tenant is its own shard with its own vector index; ~170k active tenants on 9 nodes reported | PQ / BQ / SQ / RQ per vector space |
| Vespa | Many tensor fields per document; mapped + indexed tensor = multiple vectors in one field | Field name; models switched via rank profiles | Attribute filter in query, HNSW per field | Not covered | Cell types per tensor (float, bfloat16, int8) |
| Elasticsearch | Several `dense_vector` fields per doc, each single-valued | Field name | kNN pre-filter | Index / routing (not verified) | dims max 4,096; `element_type` float / bfloat16 / byte / bit; default int8 / int4 / bbq |
| Pinecone | One dense vector per record (plus sparse / full text in document indexes) | Outside the record (index-level) | Metadata, 40 KB per record, flat JSON | Namespaces | Managed (not verified) |
| LanceDB | Several vector columns in a table (docs 404; background knowledge) | Column name | SQL filter | Not verified | IVF-PQ etc. |
| Chroma | One embedding per item; embedding function persisted in collection config, immutable | Collection | Metadata `where` | Collection per tenant | HNSW only |

## System of record, upsert, re-embedding

- Qdrant's migration recipe: add a new named vector for the new model, re-embed in the
  background, then drop the old vector; for a full rebuild, build a new collection and switch an
  alias atomically. https://qdrant.tech/documentation/tutorials-operations/embedding-model-migration/
- Weaviate: vectorizer and index type are immutable; changing them means a new collection plus
  data migration; adding a named vector is allowed.
- Chroma: embedding function fixed at collection creation.
- Pinecone: records carry flat metadata only, capped at 40 KB.
- No primary doc states "keep primary data elsewhere, store ids + vector + filter fields"; it is
  common practice (payload caps, flat metadata) but unverified as an official recommendation.

## Quantization and dimensions for 1–2k dims

- Qdrant: float16 "virtually no quality impact"; scalar 4x; binary 32x for high-dimensional
  centred vectors; product 64x. Binary needs rescoring against full vectors.
- Elasticsearch: int8 75 %, int4 87 %, bbq 96 % size reduction; bbq "benefits from rescoring".
- pgvector: `vector` indexable to 2,000 dims, `halfvec` to 4,000, `bit` to 64,000; README
  advises `halfvec` and binary quantization with re-ranking, plus subvector expression indexes.
  A 2,048-d classifier backbone exceeds the plain `vector` HNSW limit: index it as `halfvec` or a
  subvector. https://github.com/pgvector/pgvector
- Matryoshka: only models trained for it truncate well (sbert.net,
  https://huggingface.co/blog/matryoshka). BioCLIP is not Matryoshka-trained as far as found;
  treat truncation as a PCA/projection variant with its own key.
- Rule of thumb (third-party, unverified): ~4–6 KB per 1,536-d halfvec HNSW entry at m=16, so
  16 GB RAM holds ~2–3M vectors.

## Where pgvector stops

- Filtering: pgvector HNSW filters after the scan; 0.8.0 added `hnsw.iterative_scan`
  (strict or relaxed order) to refill results. The README lists three fixes: a b-tree on the
  filter column, partial indexes, table partitioning.
- Benchmarks are vendor or blog posts: one claims pgvectorscale 471 QPS vs Qdrant 41 at 99 %
  recall on 50M × 1,536-d, 308 vs 22 at 100M
  (https://medium.com/@anupkawarase.akz/pgvectorscale-beat-qdrant-11-5x-at-50m-vectors-your-vector-db-bill-should-scare-you-c90bbe062499);
  Qdrant claims best-in-class filtered search (1–2 ms overhead). No neutral measurement found.
  An arXiv paper on filter-agnostic search in PostgreSQL exists (https://arxiv.org/pdf/2603.23710),
  not read.
- pgvectorscale: StreamingDiskANN, statistical binary quantization, label-based filtering on
  `smallint[]` labels, relaxed ordering; parallel build does not support label filtering.
  https://github.com/timescale/pgvectorscale
- VectorChord: `vchordrq` (IVF + RaBitQ 4/8 bit), pgvector-compatible types; claims 100M ×
  768-d on one i4i.xlarge and a 100M index build in ~20 min; licence AGPLv3 / Elastic v2.
  https://github.com/tensorchord/VectorChord
- Blog-level consensus: pgvector is comfortable to a few million to low tens of millions of
  vectors per index when the index fits RAM; beyond that, quantization, pgvectorscale or
  VectorChord before leaving Postgres. No primary source fixes that threshold.

## What this means for a Postgres-first design

1. Keep the `(target_id, algorithm, key)` row model; it is the relational form of named
   vectors. Do not add a column per model.
2. First-class model identity beside the vector: algorithm FK (model, version, preprocessing)
   plus dimension and metric (normalised or not). Chroma and Weaviate pin this to the collection;
   we pin it to the algorithm row.
3. Re-embedding is add-new-key then drop-old (Qdrant recipe). Never overwrite in place; build
   the new partial index, flip readers, drop the old one.
4. Denormalise `project_id` onto the vector row (Qdrant `is_tenant`, Milvus partition key). A
   project filter must not need a join. Per-project partial indexes for big projects, or
   partitioning by project, plus `iterative_scan` for the rest.
5. Store `halfvec` in the HNSW index (and as storage if recall tests allow); 2,048-d needs it
   anyway. Keep float32 only where a head retrain needs it. Verify recall on our data.
6. Keep only ids, algorithm, key, project_id, created_at and the vector in this table; join
   after ANN for everything else.
7. Tracking, clustering, OOD and retraining are bulk reads by id or sequential scans, which no
   vector DB does better than Postgres. Only similarity search needs an ANN index.
8. Trigger to move ANN out: a single `(algorithm, key)` index over ~10M+ rows that no longer
   fits RAM, filtered recall dropping after `iterative_scan`, or index build times becoming
   operational pain. Try pgvectorscale or VectorChord first; then Qdrant as a derived index fed
   by id + vector + project_id.

## Sources

https://qdrant.tech/documentation/concepts/vectors/ ·
https://qdrant.tech/documentation/concepts/collections/ ·
https://qdrant.tech/documentation/guides/multiple-partitions/ ·
https://milvus.io/docs/multi-vector-search.md · https://milvus.io/docs/use-partition-key.md ·
https://docs.weaviate.io/weaviate/config-refs/collections ·
https://docs.weaviate.io/weaviate/concepts/data · https://docs.vespa.ai/en/tensor-user-guide.html ·
https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector ·
https://docs.pinecone.io/guides/index-data/indexing-overview ·
https://docs.trychroma.com/docs/collections/configure · https://github.com/pgvector/pgvector ·
https://github.com/timescale/pgvectorscale · https://github.com/tensorchord/VectorChord

## Could not verify

Pinecone's quantization and system-of-record guidance; LanceDB docs (404); Chroma data-model
page (404); Milvus multi-tenancy page (404); Vespa tenancy and quantization; Elasticsearch
tenancy; any neutral pgvector vs Qdrant / Milvus / Weaviate benchmark at 1M / 10M / 100M; the
"pgvector is fine until X" threshold from a primary source; whether HNSW on `halfvec` at 2,048-d
loses recall for our models.
