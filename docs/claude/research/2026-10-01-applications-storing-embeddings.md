# How open-source applications store and version embeddings

**Question.** How do larger open-source applications that use embeddings for several purposes
schema them, key them to the producing model, filter them by owner or scope, and handle a model
change? Immich, PhotoPrism, FiftyOne Brain, clip-retrieval / autofaiss, Ente, Nextcloud
Recognize, annotation tools, and any biodiversity tool.

**Produced by.** A research agent (Claude Sonnet), 2026-10-01, supervised. Nothing was read
directly: every file was fetched through a summarising tool, so quoted code and line references
are second-hand, and links point at branch heads (main or develop), not pinned commits.

## Immich (Postgres with pgvector or VectorChord)

- `smart_search`: primary key asset id, one `embedding` vector, 512 dimensions by default.
  https://github.com/immich-app/immich/blob/main/server/src/schema/tables/smart-search.table.ts
- `face_search`: keyed by face id, 512-d vector.
  https://github.com/immich-app/immich/blob/main/server/src/schema/tables/face-search.table.ts
- The model is not stored: no model-name column on either table; the CLIP model name lives in
  system config and in the query-embedding cache key.
  https://github.com/immich-app/immich/blob/main/server/src/services/search.service.ts
- Model change: the smart-info service compares old and new `clip.modelName` on config update; a
  new name truncates `smart_search` (a dimension change also deletes rows and re-casts the
  column), then re-queues every asset for encoding. A code TODO says this should perhaps ask the
  user first. https://github.com/immich-app/immich/blob/main/server/src/services/smart-info.service.ts
- Dimension handling: `setDimensionSize` deletes rows, swaps a check constraint, alters the
  column to `vector(n)` and rebuilds the index; size bounded 1–65,536; current size read from
  `pg_attribute`. https://github.com/immich-app/immich/blob/main/server/src/repositories/database.repository.ts
- Index: `vchordrq` (VectorChord) or `hnsw` (pgvector) depending on the installed extension; the
  schema declares HNSW with cosine ops, `m=16`, `ef_construction=300`.
- Face clustering: a face is "core" if it has at least `minFaces` neighbours within `maxDistance`
  on a timeline-visible asset; core faces create a person, others attach to existing people;
  DBSCAN-like; a `force` flag unassigns machine-assigned faces and redoes them.
  https://github.com/immich-app/immich/blob/main/server/src/services/person.service.ts
- Filtering: smart search filters by the user's id plus partner ids; album ids validated and
  passed to the repository. https://github.com/immich-app/immich/blob/main/server/src/repositories/search.repository.ts
- Face model change: no automatic handling found; appears to be a manual reset.

## PhotoPrism

- Face embeddings as a JSON blob column per face marker, with `EmbedModel`, `DetectModel` and
  `EmbedDetail` on the row, so each vector carries its producing model.
  https://github.com/photoprism/photoprism/blob/develop/internal/entity/marker.go
- Cluster table: one row per cluster; id is a base32 SHA-1 of the centroid JSON; holds sample
  count, an acceptance radius, collision count and a narrowed collision radius.
  https://github.com/photoprism/photoprism/blob/develop/internal/entity/face.go
- Merging: manually added clusters merged in up to 11 passes with union-find.
  https://github.com/photoprism/photoprism/blob/develop/internal/photoprism/faces_optimize.go
- No ANN; matching is distance computation in Go.

## FiftyOne and FiftyOne Brain

- Config records the model: the similarity API stores `model` (instance or zoo name),
  `model_kwargs`, `embeddings_field`, `patches_field`, `roi_field` in a named brain run keyed by
  `brain_key`; several runs coexist per dataset. https://docs.voxel51.com/api/fiftyone.brain.similarity.html
- Storage: embeddings are a sample field or live inside the index.
- Backends: sklearn, Qdrant, Redis, Pinecone, MongoDB, Elasticsearch, Milvus, LanceDB, pgvector,
  each a file under https://github.com/voxel51/fiftyone-brain/tree/develop/fiftyone/brain/internal/core
- Model change: new brain key and recompute; the index supports adding and removing samples.

## clip-retrieval and autofaiss

- Layout: `img_emb/*.npy`, `metadata/*.parquet` and FAISS indices; rows align by position, not
  by a key column. https://github.com/rom1504/clip-retrieval/blob/main/README.md
- Many models at once: a backend config lists named indices, each with its own `clip_model` and
  folder; queries pick one with `indice_name`.
- Model change: build a new index folder and register it under a new name.

## Ente

- Server schema not verified: only `file_id` and `datacenters` columns on an `embeddings` table
  were seen.
- On-device schema: PR 12610 mentions tables for faces, clip, clusters, persons and filedata;
  faces use protobuf doubles, CLIP raw float32. https://github.com/ente/ente/pull/12610
- The server holds only encrypted ML data; search runs on device; the help page says nothing on
  model versioning. https://ente.com/help/photos/features/search-and-discovery/machine-learning

## Nextcloud Recognize

- `faceVector` as a JSON array beside `fileId`, `userId`, `clusterId` and a threshold; no model
  column, no ANN seen. https://github.com/nextcloud/recognize/blob/master/lib/Db/FaceDetection.php

## Label Studio, Roboflow, Encord

Label Studio embeds with an off-the-shelf CLIP when a dataset syncs
(https://docs.humansignal.com/guide/dataset_search); Roboflow exposes CLIP embeddings through its
API; Encord supports custom embeddings and embedding plots. None publishes its storage schema.

## Biodiversity

- TreeOfLife-200M embeddings (Imageomics): one parquet config per model, e.g.
  `bioclip-2_float16` (768 dimensions, unnormalised) and `bioclip-2.5-vith14_float16` (1,024
  dimensions, L2-normalised); rows keyed by `uuid`, with taxonomy columns, sorted by taxonomy;
  DuckDB recommended as the reader.
  https://huggingface.co/datasets/imageomics/TreeOfLife-200M-Embeddings/blob/main/README.md
- The TreeOfLife vector DB demo uses Chroma with taxonomy as extra columns.
- BioCosmos (unconfirmed): a course report mentions Flyway-versioned Postgres and
  `search_records` columns choosing the embedding or experiment version; the PDF was unreadable.
- Nothing found on TrapTagger, Wildlife Insights or WildTrax storing embeddings.

## Comparison

| App | Storage | Entity key | Model key | Several models | Model change | ANN | Filter |
|---|---|---|---|---|---|---|---|
| Immich | pgvector or VectorChord column | asset id, face id | none, config only | no | truncate and re-queue | HNSW or vchordrq | user, partner, album |
| PhotoPrism | JSON blob | marker id | `EmbedModel` on row | implicit | recompute | none | subject |
| FiftyOne | field or backend index | sample id | brain run config | yes, by `brain_key` | new run | per backend | dataset view |
| clip-retrieval | npy, parquet, FAISS | row position | per-index `clip_model` | yes, named indices | new index | FAISS | index choice |
| Ente | on-device DB, encrypted sync | file id | not documented | not documented | not documented | on-device | user |
| Recognize | JSON column | file and user id | none | no | not documented | none seen | user |
| TreeOfLife | parquet | `uuid` | config name per model | yes, one config each | new config | DuckDB scans | taxonomy |

## Patterns worth copying

1. Record the model on the row or on a named run (PhotoPrism `EmbedModel`, FiftyOne brain key)
   to avoid Immich's gap of not knowing which model made a vector.
2. One model per vector column or table; Immich fixes the dimension with a check constraint so
   mixed dimensions fail loudly.
3. Separate tables or runs per model so models run side by side (FiftyOne, clip-retrieval,
   TreeOfLife).
4. Put dtype and normalisation in the config name (TreeOfLife).
5. Filter by owner and scope in SQL alongside the vector search (Immich).
6. Treat model change as a re-index job (Immich truncates, rebuilds, re-queues); a confirmation
   step would improve it.
7. Cluster with density rules plus a force flag (Immich's core-face rule and `force` reset are
   re-runnable).
8. Store per-cluster radii (PhotoPrism keeps a sample count and acceptance radius per centroid).

## Could not verify

Ente's server `embeddings` DDL and any model-version column; Immich's face-model-change handling
and exact line numbers; BioCosmos's Postgres schema; FiftyOne's `sklearn.py` and `pgvector.py`
internals (raw files 404); Immich's migrations and machine-learning service; whether any
camera-trap tool stores embeddings.
