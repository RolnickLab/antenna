# Embeddings as a long-lived asset: versioning, variants, compression, filtered ANN, clustering, OOD, retention

**Question.** Cross-cutting engineering practice around embeddings, independent of any one
database: how teams version a model and its vectors, how joint-space and multi-tap embeddings
are stored, Matryoshka truncation vs PCA, compression and recall loss, filtered and
tenant-scoped ANN, clustering and diverse sampling and OOD at scale, and retention, cost and
privacy for imagery that may include people.

**Produced by.** A research agent (Claude Sonnet), 2026-10-01, supervised. Primary sources are
vendor docs, engineering blogs and papers; gaps are listed at the end.

## 1. Model versioning and re-embedding

- Four steps recur: dual-write new rows to old and new indexes, backfill history, shadow-read to
  measure recall, cut over by an atomic alias flip; rollback is flipping the alias back. Per-vector
  metadata: `{doc_id, vector, model_name, model_version, embedding_timestamp}`.
  https://formation.dev/blog/embedding-model-upgrade-migration ·
  https://dev.to/gabrielanhaia/rag-re-indexing-without-downtime-a-dual-write-pattern-for-embeddings-2bn5 ·
  https://dev.to/gabrielanhaia/embedding-model-upgrades-without-re-indexing-100-upfront-134p
- Dual-writing only upserts breaks when the workload also deletes or edits payloads; those need
  tombstones or ordered replay (Formation).
- Two layouts (Qdrant): collection-per-model with an alias swap, or a named-vector layout where
  the new model is an extra vector in the same collection; the second avoids duplicating payloads
  and the old vector stays until deleted. Keep the source input so re-embedding needs no external
  lookup. https://qdrant.tech/documentation/tutorials-operations/embedding-model-migration/
- Pinterest's post covers feature backfill with partition-level version control and rollback,
  not embeddings specifically. https://medium.com/pinterest-engineering/how-pinterest-accelerates-ml-feature-iterations-via-effective-backfill-d67ea125519c

## 2. Multiple embeddings of the same thing

- Joint space: BioCLIP trains image and taxonomic-text encoders contrastively on mixed text types
  (taxonomic, scientific, common names), so image and taxon text vectors are comparable only as
  the projected, normalised output of the same checkpoint. https://arxiv.org/html/2311.18803v3
- Matryoshka (MRL): training makes any prefix of the vector usable; up to 14x smaller ImageNet
  embeddings at equal accuracy; truncation requires re-normalising; a 256-d shortlist followed by
  3,072-d rerank reached 99 % accuracy in one benchmark.
  https://proceedings.neurips.cc/paper_files/paper/2022/hash/c32319f4868da7613d78af9993100e42-Abstract.html ·
  https://supabase.com/blog/matryoshka-embeddings
- pgvector supports subvector expression indexes for this. https://github.com/pgvector/pgvector
- Truncating a non-MRL backbone gives no such guarantee; PCA is the fallback for a 2,048-d
  classifier tap.

## 3. Compression

- Hugging Face (text retrieval): int8 kept about 99.3 % of baseline quality; binary about
  92.5 %, rising to about 96 % with rescoring against full vectors; int8 about 3.7x faster,
  binary about 25x. https://huggingface.co/blog/embedding-quantization
- `halfvec` roughly halves storage with similar recall.
  https://neon.com/blog/dont-use-vector-use-halvec-instead-and-save-50-of-your-storage-cost
- Index limits: `vector` indexable to 2,000 dims, `halfvec` to 4,000; a 2,048-d float32 column
  cannot be HNSW-indexed, `halfvec` can (pgvector README).
- Binary quantization: pgvector recommends an expression index on the binary form, then
  re-ranking with originals.
- VectorChord indexes pgvector types with RaBitQ (4- or 8-bit) and hierarchical k-means.
  https://docs.vectorchord.ai/vectorchord/usage/indexing.html

## 4. Filtered and multi-tenant ANN

- Post-filter returns an unpredictable count, and zero results under a restrictive filter;
  pre-filter builds an allow list first. https://docs.weaviate.io/weaviate/concepts/filtering
- Selective filters degrade HNSW traversal toward brute force; Weaviate switches to flat search
  at about a 15 % match cutoff by default, so a small tenant is best served by exact search.
- Graph connectivity: in Qdrant, filtering out 96 % of points leaves under one link per node; it
  adds edges per indexed payload value and offers a tenant flag that co-locates one tenant's
  vectors. https://qdrant.tech/articles/filtered-vector-search-acorn/
- ACORN widens neighbour exploration at build time (ACORN-gamma) or query time (ACORN-1) so a
  filter does not disconnect the graph.
  https://mohakchugh.is-a.dev/blog/acorn-predicate-agnostic-filtered-vector-search-hnsw
- pgvector 0.8.0: iterative scans (`hnsw.iterative_scan`, default `max_scan_tuples` 20,000)
  fetch more results when the filter removes candidates; the README suggests partial indexes for
  selective filters and partitioning for high-cardinality ones.
- VectorChord can evaluate the filter before computing distances.
  https://docs.vectorchord.ai/vectorchord/usage/search.html

## 5. Beyond nearest neighbour

- kNN OOD: deep kNN distance on normalised features beats the Mahalanobis baseline SSD+ by
  24.77 % FPR@TPR95 on ImageNet-1k and avoids covariance inversion; it needs the training-set
  vectors. https://arxiv.org/pdf/2204.06507
- Clustering: FAISS k-means on 1M points × 256-d to 20,000 centroids took 55 s on one P100; 95M
  × 128-d to 85k centroids under an hour on 7 GPUs.
  https://github.com/facebookresearch/faiss/wiki/Low-level-benchmarks/Indexing-1T-vectors
  Plain HDBSCAN reportedly does not scale much past a million points; UMAP-first or cuML is the
  usual workaround. https://opendatascience.com/?p=50975
- Diverse sampling: k-center greedy (farthest-first) core-set is the standard method for picking
  spread-out images (Sener and Savarese, ICLR 2018). https://arxiv.org/abs/1708.00489

## 6. Retention, cost and privacy

- Hugging Face's 250M × 1,024-d example: int8 is 4x and binary about 32x smaller than float32.
  Arithmetic per million vectors, no index: 1,024-d is 4.1 GB float32, 2.0 GB float16, 1.0 GB
  int8; 2,048-d is 8.2, 4.1 and 2.0 GB.
- Derived data: migration guides treat vectors as recomputable from source plus model version,
  which requires retaining the crops and a pinned checkpoint (Qdrant guide above).
- Inversion: face embeddings can be inverted to approximate faces and leak soft attributes
  (https://arxiv.org/pdf/2304.05561, https://arxiv.org/html/2504.18015v3); CLIP image embeddings
  are reconstructible (https://arxiv.org/html/2508.00756v3).
- GDPR, per secondary summaries of EDPB guidance: footage is personal data; it becomes Article 9
  biometric data only when processed to uniquely identify someone
  (https://www.eurosmart.com/?id=87&na=v,
  https://www.dataprotectionreport.com/2024/07/edpb-opines-on-the-use-of-facial-recognition-in-airports).
  Insect-crop embeddings are lower risk; whole-capture embeddings of frames that may contain
  people are the exposure.

## Practices to adopt

1. Record on every vector (or on a model-registry row it references): model name, checkpoint
   hash, preprocessing version, tap (backbone or projection), dimension, normalisation flag,
   created-at.
2. One table per (entity, model), or a model FK plus a partial index per model. Never mix
   models in one index.
3. Migrate by dual-write, batch backfill from crops, shadow-compare neighbour overlap, then flip
   a "current model" pointer. Keep the old column until sign-off.
4. Retain crops and pinned weights so vectors stay droppable and recomputable.
5. Store `halfvec` by default: the only way to HNSW-index 2,048-d, and it halves storage.
6. Store a reduced variant only for a measured need: an MRL prefix index, or PCA for non-MRL
   backbones. Compute UMAP on the fly, never as source of truth.
7. Keep BioCLIP image and taxon text vectors normalised, same checkpoint, same tap, so
   zero-shot works.
8. Filter per project by pre-filtering on project id: exact scan for small projects, partial or
   partitioned indexes for large ones, iterative scans plus higher `ef_search` in between.
9. Store class centroids in a separate table keyed by (model, taxon, scope) with member count,
   algorithm and member-set version; recompute from items.
10. Keep per-item vectors where kNN OOD or head retraining needs them. Flag or exclude captures
    where people are detected.

## Could not verify

Spotify, Etsy, Shopify, Instacart, LinkedIn, Airbnb or Zalando posts on embedding-model
migration (only vendor docs and blogs surfaced; Pinterest's post is about feature backfill);
recall loss for ~1k-d image embeddings specifically (quantization figures are text-retrieval
results); published guidance on storing per-class centroids beside per-item vectors;
primary-source HDBSCAN scale limits; a formal GDPR ruling on embeddings of incidental imagery;
which BioCLIP tap is best for retrieval vs head training.
