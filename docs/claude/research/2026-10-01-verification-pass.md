# Verification pass, 2026-10-01

Method: primary sources fetched on this date, plus read-only SELECTs on two local database copies. No database was written.

## A. Django and ORM

**1. Django 4.2 is enough: VERIFIED, with one spelling trap.**
- `UniqueConstraint(condition=Q(...))` exists in 4.2 (docs.djangoproject.com/en/4.2/ref/models/constraints/).
- In 4.2 `CheckConstraint` takes `check=`, not `condition=`. The `condition=` spelling arrives in 5.1.
- Lookups are usable as conditional expressions since Django 4.0 (release notes: "Lookup expressions may now be used in QuerySet annotations, aggregations, and directly in filters"). So `Q(Exact(Func(..., function="num_nonnulls"), 1))` is legal on 4.2. I could not compile it here: the local Python has Django 5.2, not 4.2.
- A composite FK added with `RunSQL` is invisible to Django, so it sits beside a normal `ForeignKey` without conflict. Migration state needs `SeparateDatabaseAndState` only if the model should know about it.
- pgvector-python: the changelog shows `halfvec` support for Django since 0.3.0. At v0.5.0, `HalfVectorField(dimensions=None)` returns `db_type` `halfvec` (unsized). `Avg` over a vector field is documented in the README. `CosineDistance` is supported. The extension defines `avg(halfvec)`.
- v0.5.0 declares `requires-python >= 3.10` and lists Django unpinned, so the README gives no Django floor. I did not find a stated minimum.
- Pins: `requirements/base.txt` on the local checkout has no pgvector line (Django 4.2.10 only). `origin/feat/occurrence-history-and-embeddings` and `feat/tracking-ui` both pin `pgvector==0.5.0`.
- Meaning: no Django upgrade is needed. Use `check=`, and check the project's Python is 3.10 or newer.

**2. Django 5.2 `CompositePrimaryKey`: REFUTED as a route.** The 5.2 docs say `ForeignKey` "currently cannot reference models with composite primary keys". The workaround is `ForeignObject`, an internal API that creates no constraint or index. Meaning: composite FKs stay in raw SQL, so there is no reason to upgrade for this.

**3. `fix_missing_relationships`: VERIFIED.** It loops over all Events. For an Event with no deployment it borrows the deployment from one of its captures, else one of its occurrences, and saves it. Otherwise it logs "recommend deleting". The `--dry-run` flag is parsed but never read, so a dry run still writes. It repairs only the event-to-deployment link and nothing about project. Meaning: it is no precedent for a project backfill, and the flag bug should be fixed before anyone relies on it.

## B. PostgreSQL and pgvector

**4. Composite FK with NULLs: VERIFIED from the PostgreSQL 16 docs (ddl-constraints).**
- "Normally, a referencing row need not satisfy the foreign key constraint if any of its referencing columns are null." This is the default `MATCH SIMPLE`.
- The remedy quoted: declare the referencing columns `NOT NULL`.
- A FK "must reference columns that either are a primary key or form a unique constraint". `UNIQUE (id, project_id)` is therefore the required target. It is accepted with a nullable `project_id`, because NULLs never conflict, and `id` is already unique.
- `ON UPDATE CASCADE` "means that the updated values of the referenced column(s) should be copied into the referencing row(s)". A changed parent project propagates, so children rows move with it. Children with NULL are never matched.
- I did not run these as a test because a temp table counts as a write. They rest on the docs only.
- Meaning: a nullable child project column silently opts that row out of the guarantee. Make it `NOT NULL` where the guarantee matters.

**5. pgvector versions: VERIFIED (README and CHANGELOG at tag v0.8.0).**
- `halfvec` was added in 0.7.0 (2024-04-29). Iterative index scans were added in 0.8.0 (2024-10-30).
- HNSW and IVFFlat limits: `vector` up to 2,000 dimensions, `halfvec` up to 4,000. Storage limit: 16,000 dimensions for both.
- `CREATE CAST (real[] AS halfvec)` exists in `sql/vector.sql`, along with integer, double and numeric arrays.
- Dockerfile: the local checkout's postgres Dockerfile installs no pgvector. Both `origin/feat/occurrence-history-and-embeddings` and `feat/tracking-ui` install `postgresql-16-pgvector=0.8.*`.
- Installed extension versions: the production-copy database reports 0.5.1. The tracking demo database reports 0.8.6. Both run PostgreSQL 16.15.
- Meaning: the production copy cannot create `halfvec` (needs 0.7.0) or iterative scans (0.8.0) until its extension is upgraded. A `halfvec` design depends on that upgrade in every environment.

**6. float16 recall: PARTIALLY VERIFIED; the 1024-d case is STILL OPEN.**
- The tracking demo database holds 0 rows in the detection embedding table, not ~12k. It has 99 rows of 2048-d classification features. The production copy has 113 rows in the detection table and 604 classification feature rows, all 2048-d.
- So I sampled 600 random 2048-d classification vectors from the production copy. numpy 2.3.5 was available.
- Result: mean top-10 overlap 0.853. Top-1 agreement 0.982. Max absolute cosine change 1.5e-4 (mean 1.6e-5).
- The low overlap is a tie artifact. This sample has 3,470 pairs with cosine above 0.9999. The worst float16 pick is within 1.9e-6 of the true 10th-neighbour similarity.
- Meaning: float16 moves similarities by about 1e-4, which does not change retrieval quality in any meaningful way. Re-run on real 1024-d BioCLIP vectors before citing a number for them.

**7. NATS payload: REFUTED as a risk for results.**
- The local compose runs `nats:2.10-alpine` with only `-js -m 8222`. Nothing in the compose files or `nats_queue.py` sets `max_payload`. The server default is 1MB (docs.nats.io configuration page), with advice not to exceed 8MB and a ceiling of 64MB.
- Estimate (not measured): one array of 2,497 floats at 6 decimals is about 26 KB of JSON text. A batch of 8 images x 15 detections is about 3 MB of logits, so it would exceed the default roughly threefold. Full-precision float reprs would roughly double that.
- However, the only `publish` in `nats_queue.py` sends task messages. Results are POSTed to the job result endpoint over HTTP and then handled by Celery.
- Meaning: the 1 MB limit does not constrain logits today. It would bind if results were ever moved onto NATS.

## C. Literature

**8. BioCLIP embedding choice: VERIFIED for retrieval; no support for a pre-projection head.**
- open_clip `encode_image` returns the output after the final projection (`pooled @ self.proj` in `transformer.py`), optionally L2-normalised.
- The BioCLIP paper (arXiv 2311.18803, few-shot section) does not use a linear probe. It uses a SimpleShot nearest-centroid classifier on "the image embedding from the visual encoder", with mean subtraction and L2-normalisation.
- Meaning: store the projected embedding, normalise it at use. The paper gives no basis for preferring the pre-projection feature.

**9. Neutral benchmark at 1M or more: STILL OPEN.**
- ann-benchmarks.com lists pgvector among 37 algorithms on 9 datasets. The page shows no run date and no numbers I could extract. I did not confirm dataset sizes from the page itself.
- VectorDBBench (github.com/zilliztech/VectorDBBench) includes PgVector with 1M and 10M cases. It states "VDBBench is sponsored by Zilliz", the Milvus vendor, so it is not neutral. Its leaderboard is at zilliz.com/benchmark, which I did not read.
- Meaning: no defensible pgvector-versus-dedicated-store number is available from this pass.

**10. Immich model change: VERIFIED for CLIP, with no equivalent found for faces.** Pinned commit 02063972e82b1bfd17b6fc2e3b3ff39936229ea5, `server/src/services/smart-info.service.ts`.
- On a CLIP model name change, `onConfigUpdate` either resizes the vector column (when the dimension differs) or calls `deleteAllSearchEmbeddings()`.
- It does not re-queue. The code says: "TODO: A job to reindex all assets should be scheduled, though user confirmation should probably be requested before doing that."
- In-flight jobs return `Skipped` when the model changed since the embedding was made.
- `person.service.ts` at that commit has no config-update handler that compares the face model name. I found no automatic reset for faces, from absence in that file only.
- Meaning: Immich treats a model change as destructive and manual: embeddings are dropped and the user chooses when to regenerate.

## Summary

| Item | Verdict | Consequence |
|---|---|---|
| 1 Django 4.2 sufficiency | Verified | No upgrade. Use `check=`. Python 3.10 or newer for pgvector-python 0.5.0. |
| 2 Composite PK as FK target | Refuted | Composite FKs stay raw SQL. |
| 3 fix_missing_relationships | Verified | Only repairs event deployment. Its dry-run flag is ignored. |
| 4 Composite FK and NULLs | Verified (docs only) | Nullable child project opts out. Use NOT NULL. |
| 5 pgvector versions | Verified | Production copy is 0.5.1. Needs 0.7.0 for halfvec, 0.8.0 for iterative scans. |
| 6 float16 recall | Partial | 2048-d: similarity shift 1.5e-4, ties explain overlap. 1024-d not measured. |
| 7 NATS payload | Refuted | Default 1 MB. Results go over HTTP, not NATS. |
| 8 BioCLIP output | Verified | Use the projected, normalised embedding. |
| 9 Neutral benchmark | Still open | Only vendor-run numbers found. |
| 10 Immich model change | Verified (CLIP) | Drops embeddings, no re-queue. Faces not found. |

No local paths, hostnames, credentials or project ids appear in this file.
