# Research notes

External research gathered for design work, one file per question. Each note records the
question that was asked, who or what produced the answer, the sources, and an explicit list of
what could not be verified. Design documents under `../planning/` cite these notes instead of
repeating them.

Conventions:

- File name: `YYYY-MM-DD-<topic>.md`.
- Header block: question, produced by (a person, or a research agent and its model), date,
  caveats on how sources were read (summarising fetches, branch heads vs pinned commits).
- Body: the findings with a URL or permalink per claim, then "What transfers to Antenna", then
  "Could not verify". Claims without a source are marked as the author's reasoning.
- Public repository: no hostnames, deployment or customer names, local paths, project or job ids.

| Date | Note | Question |
|---|---|---|
| 2026-09-29 | [MLOps prediction stores and run provenance](2026-09-29-mlops-prediction-stores-and-provenance.md) | How do ML platforms store per-input outputs, run provenance and derived-model lineage? |
| 2026-09-29 | [PostgreSQL float arrays and pgvector](2026-09-29-postgres-float-arrays-and-pgvector.md) | How should wide float arrays (embeddings, logits) be stored in PostgreSQL 16? |
| 2026-09-29 | [Biodiversity and annotation platforms: machine vs human records](2026-09-29-biodiversity-and-annotation-platforms.md) | How do camera-trap, citizen-science and annotation tools separate model predictions from human verification? |
| 2026-09-29 | [Polymorphic output tables and naming](2026-09-29-polymorphic-output-tables-and-naming.md) | One table with an exclusive-arc FK or one table per target? What are these things called elsewhere? |
| 2026-10-01 | [InvokeAI storage schema](2026-10-01-invokeai-storage-schema.md) | How does a graph-execution app store sessions, intermediate tensors, images and model records? |
| 2026-10-01 | [Denormalised project foreign key](2026-10-01-denormalised-project-fk.md) | What does Antenna do today to keep copied `project` columns in sync, and what do Django and PostgreSQL offer? |
| 2026-10-01 | [Vector database data models](2026-10-01-vector-database-data-models.md) | How do Qdrant, Milvus, Weaviate, Vespa, Elasticsearch, Pinecone, LanceDB and Chroma model several vectors per entity, tenancy and filtering? |
| 2026-10-01 | [Applications storing embeddings](2026-10-01-applications-storing-embeddings.md) | How do Immich, PhotoPrism, FiftyOne, clip-retrieval, Ente, Nextcloud Recognize and TreeOfLife store and version embeddings? |
| 2026-10-01 | [Embedding lifecycle practices](2026-10-01-embedding-lifecycle-practices.md) | Model versioning, multiple embeddings per item, compression, filtered ANN, clustering and OOD, retention and privacy. |
| 2026-10-01 | [Verification pass](2026-10-01-verification-pass.md) | Settles ten items the notes above could not verify: Django 4.2 sufficiency, composite FK semantics, pgvector versions, float16 neighbour agreement, NATS payload, BioCLIP output choice, Immich model change. |

Consumers: `../planning/2026-10-02-model-outputs-and-review-design.md`,
`../planning/2026-10-01-project-fk-denormalization-ticket-draft.md`.
