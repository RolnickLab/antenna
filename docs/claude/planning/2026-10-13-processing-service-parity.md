# Processing-service parity: template services vs ADC (2026-10-13)

Branch `feat/processing-service-parity`, stacked on #1462 (`feat/detection-embeddings-task`, 0048796c).
Reference: ADC `origin/feat/bioclip-features-all-detections` (ADC PR #175, a8047bd, includes #172).
Status: inventory + plan, written before any code. AI-agent working doc.

ADC file refs below use: `S` = `trapdata/api/schemas.py`, `A` = `trapdata/api/api.py`,
`FE` = `trapdata/api/models/feature_extraction.py`, `C` = `trapdata/api/models/classification.py`,
`ST` = `trapdata/settings.py`, `W` = `trapdata/antenna/worker.py`, `R` = `trapdata/antenna/registration.py`.

Gap legend: **T** = missing in template services (minimal/example) · **AN** = missing or different in
Antenna (`ami/ml/schemas.py`, `ami/ml/models/pipeline.py`) · **ADC** = ADC-only by design, or an ADC
gap to report (not fixed here) · **OK** = already in parity.

## 1. Inventory

### 1.1 GET /info

| Item | ADC #175 | minimal | example | Antenna schema | Gap |
|---|---|---|---|---|---|
| `ProcessingServiceInfoResponse` | `name, description, pipelines` (S:413) | same | same | adds `algorithms` list (schemas.py:358) | OK (Antenna superset) |
| `PipelineConfigResponse` | `name, slug, version, description, algorithms, stages` (S:402); `stages` never filled | same, `stages` unused | same | same | OK |
| `AlgorithmConfigResponse` | `name, key, description, task_type, version, version_name, uri, category_map` (S:247) | same | same | same | OK |
| Detector task_type | `"localization"` (models/localization.py:12) | `"detection"` | `"detection"` | enum accepts both (`AlgorithmTaskType`, algorithm.py:191) | OK; doc both |
| Embedding algorithm | `task_type="embedding"`, `category_map=None`, key `bioclip_2_5_embeddings` (A:232) | **none** | **none** | stored when listed; unlisted key → `PipelineNotConfigured` | **T** |
| Extractor in classifier pipelines | appended to `pipeline.algorithms` when `AMI_EMBEDDING_EXTRACTOR` set (A:295) | n/a | n/a | needs it listed to store | **T** |
| Feature-only pipeline | `bioclip_2_5_features`, algorithms `[detector, extractor]` (A:265) | **none** | **none** | #1479 `is_embedding_only()` = *all* algorithms are embedding → **False** for ADC's shape | **T**, and **AN (#1479)** see §3.2 |
| Category map rows | `{index, label, taxon_rank}`, `labels`, `uri` (A:183) | `{index, gbif_key, label, source, taxon_rank}` | from HF `id2label` | `data`, `labels`, `version`, `description`, `uri` | OK |

### 1.2 POST /process — request

| Item | ADC #175 | minimal | example | Antenna sends | Gap |
|---|---|---|---|---|---|
| `pipeline` | enum of *selected* slugs (A:308); unselected → 422 | `Literal` of 3 slugs (only 2 exist) | `Literal` | `str` | OK |
| `config` type | `PipelineConfigRequest`, extra keys ignored (pydantic v2 default) | `config: dict` **required**, then **ignored** | typed, optional, read for `candidate_labels` | full `Pipeline.get_config(project)` dict, including Antenna-only `request_*` and `reprocess_existing_detections` | **T** |
| `include_logits` | `bool=True` (A:416, A:457) | ignored; random classifiers always send logits, constant never | ignored | only if project/pipeline config sets it | **T** |
| `include_features` | `bool=False`; fills `ClassificationResponse.features` (2048-d) | ignored | ignored | no `features` field on `ClassificationResponse` → silently dropped | **ADC** (legacy, superseded by `embeddings`) |
| `features_for_all_detections` | `bool\|None`; `None` → `AMI_FEATURES_FOR_ALL_DETECTIONS`; species-classifier vector on *every* detection incl. non-moths, keyed by classifier (C:232) | ignored | ignored | via config | **T** |
| `embedding_extractor` | `str\|None`; `None` → env; `""` off; unknown key → 422; on classifier pipelines any key other than the advertised one → 422 (A:356) | ignored | ignored | via config | **T** |
| `example_config_param` | `int\|None` | – | – | – | ADC (example only) |
| `detections` on classifier pipelines | **ignored**; detector runs again (S:349) | **used**: detector skipped, classifier runs on sent boxes | used | sent when project flag `reprocess_existing_detections` is on (pipeline.py:378) | **ADC gap** to report: the Antenna flag has no effect against ADC |
| `detections` on feature-only pipeline | echoed: same `bbox`, `algorithm`, `crop_image_url`; no/zero-area bbox skipped; missing source images added (A:516) | n/a | n/a | `process_detections` (#1479) | **T** |
| `DetectionRequest.bbox` | optional | **required** | required | optional (schemas.py:170) | **T** |

### 1.3 POST /process — response

| Item | ADC #175 | minimal | Antenna | Gap |
|---|---|---|---|---|
| `DetectionResponse.embeddings` | `list[EmbeddingResponse]\|None`, ≤1 per algorithm key (FE:18) | **missing** | present (schemas.py:200) | **T** |
| `EmbeddingResponse` | `features: list[float]`, `algorithm: AlgorithmReference` (S:118) | missing | same, non-empty validator | **T** |
| `ClassificationResponse.logits` | `list[float]\|None` | `list[float]=[]` | `list[float]\|None` | OK (minor) |
| `ClassificationResponse.features` | present | absent | absent | **ADC**, see P2 |
| Feature-only classifications | `[]` | n/a | #1479 writer ignores classifications and the echoed detector | **T** |
| `PipelineResultsResponse.algorithms` | always `{}` (filled var never passed, A:492) | omitted | deprecated | ADC quirk, harmless |
| `PipelineResultsResponse.config` | always defaults, not echoed | – | absent → ignored | ADC quirk, harmless |
| `errors` | – | **missing** | `list\|str\|None` | T (minor, example has it) |

### 1.4 Health

| | ADC | minimal / example | Gap |
|---|---|---|---|
| `/livez` | `200 {"status": true}` | same | OK |
| `/readyz` | `200 {"status": [selected slugs]}`, `503 {"status": []}` | same over all slugs | OK |

### 1.5 Pipeline selection (#172)

ADC: `AMI_PIPELINES` (ST:87), comma-separated slugs, whitespace-stripped, empty = all; unknown slug
raises at startup; only selected pipelines appear in /info and `PipelineChoice`. Minimal/example: none. **T**.

### 1.6 Antenna request building

| Path | Config sent | Notes |
|---|---|---|
| Sync / push (`process_images`, pipeline.py:325) | `Pipeline.get_config(project_id)` = `default_config` updated with `ProjectPipelineConfig.config` | **AN bug**: `get_config` calls `.update()` on `self.default_config` in place (pipeline.py:1300), so one project's overrides leak into the next call on the same `Pipeline` instance |
| Sync, job loop (`jobs/models.py:575`) | same call; reads `request_source_image_batch_size` Antenna-side | key is still forwarded to the service; services must ignore unknown keys (ADC does) |
| Async / pull (`PipelineProcessingTask`, schemas.py:279) | **none** | ADC worker reads flags from env only (W:512), never runs the extractor, registers without it (R:111). **AN + ADC**, follow-up |
| `process_detections` (#1479, not on this branch) | `get_config(project_id)` | sends stored boxes; expects an echo with embeddings |

### 1.7 Template-service hygiene found on the way

- `minimal/api/test.py` imports `RandomPipeline`, which no longer exists; the file cannot run.
- `minimal` `PipelineChoice` lists `"random"`, which has no pipeline.
- `schemas.py` is copied three times (minimal, example, Antenna) and has drifted (bbox optional,
  `embeddings`, `errors`, `config` typing). Separate Docker build contexts make a shared module awkward;
  this PR keeps the copies but aligns them, and the README names Antenna's `ami/ml/schemas.py` as the source of truth.

## 2. Plan

### 2.1 minimal service (stand-in for ADC, no weights, deterministic)

1. **Schemas**: `EmbeddingResponse`; `DetectionResponse.embeddings`; `DetectionRequest.bbox` optional;
   `PipelineRequestConfig` with `include_logits=True`, `features_for_all_detections=False`,
   `embedding_extractor: str|None=None`, unknown keys ignored; `PipelineRequest.config` optional;
   `errors` on results; `PipelineChoice` derived from registered slugs (drop the dead `"random"`).
2. **Deterministic vectors**: SHA-256 of `"{algorithm_key}:{source_image_id}:{bbox}"` → floats, L2-normalised.
   Same box ⇒ same vector; different boxes ⇒ different vectors (so similarity sort #1509 has signal).
   Lengths fixed and documented: **8** for the feature extractor, **4** for a classifier's backbone vector.
   Two lengths on purpose: Antenna checks length per (algorithm, key), and real services differ (ADC 1024 vs 2048).
3. **New algorithm** `constant-feature-extractor` (`task_type="embedding"`, no category map).
4. **Pipelines** (existing `constant` and `random-detection-random-species` keep their algorithm lists,
   because every live-service test registers them):
   - `constant`, `random-detection-random-species`: honour `include_logits` and `features_for_all_detections`
     (vector keyed by the terminal classifier, already listed). No new algorithms.
   - **new** `constant-with-feature-extractor`: constant detector + constant classifier + extractor.
     Extractor on unless `embedding_extractor == ""`; any other key than the advertised one → 422 (ADC rule).
     Stand-in for an ADC deployment with `AMI_EMBEDDING_EXTRACTOR` set. Difference: default is per pipeline, not env.
   - **new** feature-only `constant-feature-extractor-only` with algorithms `[constant-detector, extractor]`
     (ADC's shape). With request detections: echo each box (`bbox`, `algorithm`, `crop_image_url`)
     with one embedding, no classifications, skip missing/zero-area boxes, add missing source images.
     Without detections: run the constant detector, then embed.
5. **`AMI_PIPELINES`**: same name and semantics as ADC #172; unknown slug fails startup.
6. **Service tests**: replace the dead `api/test.py` with `fastapi.testclient` tests (image loading patched),
   runnable with `docker compose -f docker-compose.ci.yml run --rm ml_backend python -m unittest`.
   Adds `httpx` to minimal requirements if TestClient needs it.

### 2.2 example service

Align `schemas.py` (accept the same config keys and optional bbox; `embeddings` on the response) so it
accepts everything Antenna sends. It does **not** produce vectors: its HF models would need a pooled-feature
path and weights; documented in the README as the reason it differs. Re-check after reading prior-work PRs (§4).

### 2.3 Antenna

- **Not fixed here:** the `Pipeline.get_config` in-place mutation. Open PR #1279 (base main) makes the same one-line copy
  and adds `config` to the NATS task; duplicating it would conflict. The e2e tests below fetch a fresh `Pipeline` per test,
  so the leak cannot affect them.
- **E2E tests** against the `ml_backend` container (new class beside `TestPipelineWithProcessingService`, ami/ml/tests.py:282):
  1. `constant-with-feature-extractor` → `process_images` → `save_results`: one `DetectionEmbedding` per detection,
     algorithm = extractor, length 8; classifications still saved.
  2. Project config forwarded: `ProjectPipelineConfig.config = {"features_for_all_detections": True, "embedding_extractor": ""}`
     → stored vectors come from the classifier (length 4) and none from the extractor. The service's output depends on the
     config, so this proves forwarding without mocking the HTTP call.
  3. Feature-only via `process_detections` + `save_embedding_results`: echoed boxes match stored detections, no new
     detections/classifications/occurrences. **Needs #1479's code** (see §3.1).
  4. Feature-only pipeline run as a regular ML job: decide expected behaviour after §3.2.
- Existing tests that count pipelines or register the service: re-run whole `ami.ml` + `ami.main` suites.

### 2.4 Schema proposals (`ami/ml/schemas.py`, no Antenna concepts)

- **P1** Document the known request config keys in `PipelineRequestConfigParameters`' docstring
  (`include_logits`, `features_for_all_detections`, `embedding_extractor`; `include_features` is legacy and ignored)
  and state that services must ignore unknown keys (Antenna sends `request_*` and `reprocess_existing_detections`).
  Keep it a `dict` subclass: `Pipeline.default_config` is a `SchemaField` over it, and a typed schema would change the
  field definition (migration) and reject configs already stored. Typed validation can come with a later admin form.
- **P2** Do **not** add `ClassificationResponse.features`. Vectors travel on `DetectionResponse.embeddings`
  (one place, keyed by algorithm, includes non-moths). ADC's `include_features` stays ADC-only.
- **P3** Async config (`PipelineProcessingTask` has none; ADC worker is env-only): out of scope. Already owned by
  issue #1422 (config in push and pull mode, per project and per job), PR #1279 (Antenna side) and ADC #146 (worker echoes it).
  #1279 does not *use* config during inference, so which per-request keys a pull-mode worker honours is still undecided;
  the keys documented here (P1) are the sync-mode contract ADC already implements and should feed #1422's typed proposal.

### 2.5 README

New "Contract" section in `processing_services/README.md`: endpoints, `/info` task types (incl. `embedding`,
`detection`/`localization`), the request config keys and the "ignore unknown keys" rule, `embeddings` on detections
(one per algorithm, list every algorithm in /info or Antenna rejects the batch), feature-only pipelines (echo boxes,
keep `algorithm`, no classifications), vector lengths fixed per algorithm, `AMI_PIPELINES`, and sync vs async config.

### 2.6 Verification gate before push

Full backend suite serially, own compose project `-p antenna-ci-psparity`, explicit `-f docker-compose.ci.yml`,
recreate test DB + `FLUSHALL`; `makemigrations --check --dry-run`; pre-commit. Heavy steps under
`systemd-run --user --scope -p MemoryHigh=24G` (BEAST: 22 GB available, swap full, 20 GB disk free at start).

## 3. Open questions (sent to the originating session)

1. **Base for test 3.** `process_detections` lives on #1479 (`feat/add-feature-vectors-task`), not #1462.
   Options: (a) base this branch on #1479 (stack main ← #1462 ← #1479 ← this); (b) keep #1462 base and add test 3
   in a follow-up after #1479 lands. Leaning (a): nothing is committed yet, so rebasing costs nothing.
2. **#1479 `is_embedding_only()`** returns False for ADC's `bioclip_2_5_features` (`[detector, extractor]`).
   So `raise_if_embedding_only` will not stop an ML job on ADC's feature pipeline; that job would detect, embed and
   save detections without classifications. A predicate like "has an embedding algorithm and no classification
   algorithm" would match both shapes. Commit 394d0efb on #1462 already treats detector+extractor as a valid shape.
3. **ADC gaps to report, not fix here** (owner decides whether to file): classifier pipelines ignore request
   detections (Antenna's `reprocess_existing_detections` flag has no effect); `response.algorithms` never filled;
   async worker has no per-job config and no extractor.

## 4. Prior work

Keyword search over antenna + ADC PRs/issues (gh), bodies skimmed. Possibly incomplete.

| Topic | PR / issue | State | Relevance here |
|---|---|---|---|
| Templates origin | antenna #798 | merged 2025-04-30 | created minimal + example |
| Reprocess existing detections | antenna #815 | merged 2025-08-16 | why minimal classifier pipelines use request detections; ADC classifier pipelines do not |
| Register before process | antenna #942 | merged | every returned algorithm key must be in /info |
| Global moths classifier in `example` | antenna #992 (`feat/global-moths-model`) | open, stale since 2025-11 | natural place for real vectors in `example` (ResNet50 backbone = ADC's 2048-d `forward_with_features`); not touched here |
| Real classifiers in local dev | antenna #952 | open draft | local `ml_backend` from `example`, CI keeps `minimal`: confirms minimal is the CI stand-in |
| Other detectors | antenna #1089 flat-bug (draft), ADC #160 stage-list pipelines + YOLO26, ADC #141 Mothbot YOLO11m | open | detector choice is ADC #160's design; out of scope |
| Batching | ADC #113 async posting (merged), ADC #149 split oversized uploads (open), ADC #110 batched classification (merged), antenna #1223 decouple result ingestion (issue) | mixed | payload size: ~29k-class scores/logits already reach 110-142 MB per batch; vectors add 1024-2048 floats per detection. Stand-ins stay tiny; README should mention `include_logits` as the size lever |
| Minimal as v2 worker | antenna #1252 (draft) | open | edits `minimal/api/schemas.py`, `Dockerfile`, adds `register.py`/`worker/`. Keep this PR's minimal schema changes additive to limit conflicts |
| Config in pull mode | issue #1422, antenna #1279, ADC #146 | open | see P3; #1279 also fixes `get_config` |
| Service auth | antenna #1194 | open | touches minimal `register.py`/`start.sh` (not on main) |
| Vectors | #1462, #1479, #1509, #1500, #1510; ADC #170, #175, #77, #123 | open | this PR's dependencies / consumers |

Lessons: registration is add-only (renamed slugs linger), so new pipeline slugs should be final names;
an earlier BioCLIP service lived in `processing_services/` and moved to ADC (8ec3704f), so real vector models belong in ADC, not here.
