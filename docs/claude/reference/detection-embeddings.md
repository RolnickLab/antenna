# Detection embeddings (feature vectors)

Reference for agents. How Antenna stores a feature vector for every detection, how a
feature-only pipeline fills them in for existing detections, and how tracking picks which
extractor's vectors to compare. See #1417 for the original design.

## Storage

- `DetectionEmbedding` (`ami/main/models.py`, migration `main/0102_detection_embeddings_and_output_jobs.py`):
  concrete table under two abstract bases, `AlgorithmOutput` (algorithm, job, timestamp) and
  `Embedding` (project, key, vector, `EmbeddingQuerySet`). One row per (detection, algorithm, key),
  unique constraint `main_detectionembedding_unique_detection_algorithm_key` (its index leads with
  `detection_id` and serves reads). `key` defaults to `embedding` (the backbone vector); vectors
  are comparable only within one (algorithm, key). `vector` is an unsized pgvector `halfvec`
  with `STORAGE EXTERNAL` (needs pgvector >= 0.7): extractors differ (2048 for the moth classifier
  backbones, 1024 for BioCLIP). `job` FK is `RESTRICT` (a job with vectors cannot be deleted on
  its own; `JobViewSet.perform_destroy` answers 409) and nullable because `save_results` can run
  without a job. `Job.deployment` is SET_NULL (`jobs/0024_job_deployment_set_null.py`, state only),
  since a CASCADE from a deleted station would hit that RESTRICT and fail the delete. `project` is NOT NULL, filled from the detection's capture by
  `fill_project_ids` (`ami/main/models_future/project_scope.py`) in `save()` and in
  `EmbeddingQuerySet.bulk_create`; `project_mismatch_counts()` reports drift.
- Draft databases that applied the earlier `main/0102_detection_embedding` (and `0103`/`0104`)
  are rebuilt, not upgraded: drop `main_detectionembedding`, delete those `django_migrations`
  rows, migrate, then replay the feature-only job.
- `Detection.job` and `Classification.job` (nullable, SET_NULL, indexed, same migration): the job
  whose results saved the row; null for older rows and jobless saves.
- `Algorithm.embedding_dimensions` (`ami/ml/models/algorithm.py`, migration `ml/0029`): the one
  length an algorithm's vectors have. Set from `/info` (`AlgorithmConfigResponse.embedding_dimensions`,
  optional) in `get_or_create_algorithm_and_category_map`, or from the first vector stored
  (`_check_embedding_dimensions` in `ami/ml/models/pipeline.py`, conditional UPDATE so concurrent
  batches agree). A vector of another length raises `EmbeddingDimensionMismatch` (a
  `PipelineNotConfigured`) and the batch stores nothing.
- Legacy: `Classification.features_2048` (vector(2048)) from classifiers run with `include_features`.
  Readers fall back to it (see below).
- No ANN index exists; one would need a fixed dimension per index (a partial index per algorithm).

## Contract with the processing service (`ami/ml/schemas.py`)

- `DetectionResponse.embeddings: list[EmbeddingResponse] | None`, each
  `{"algorithm": {"name", "key"}, "features": [float, ...]}`. The key `vector` is accepted as an
  alias (root validator). Any non-empty length; the per-algorithm length is enforced at save time.
- The algorithm key must be declared in the pipeline's `/info`, else `PipelineNotConfigured`.
- **Feature-only pipeline**: at least one algorithm has `task_type` in
  `Algorithm.feature_extraction_task_types` (`embedding` or `feature_extraction`) and none is a
  classifier (`classification` / `tagging`). Detector algorithms are allowed because the service
  lists the detector whose boxes it echoes back (`feature_extractors_if_feature_only()` in
  `ami/ml/models/pipeline.py`, `Pipeline.feature_extraction_algorithms()` returns only the extractors).
- Request for a feature-only run (sync, `process_images`): `PipelineRequest` with
  `source_images` = only the images that still have a detection to embed, and `detections` =
  those detections as `DetectionRequest{source_image, bbox, crop_image_url, algorithm=<original
  detector ref>}` (`collect_detections_for_features`, one query). Async (NATS): the same list on
  `PipelineProcessingTask.detections` (`_attach_detections_for_feature_pipeline` in
  `ami/ml/orchestration/jobs.py`). The service must return the same boxes, each with embeddings,
  and no new boxes.

## Write path

- `save_results` (`ami/ml/models/pipeline.py`): if the pipeline is feature-only it calls
  `save_features_for_existing_detections` and returns. That path matches response boxes to
  existing real detections by `(source_image_id, bbox rounded to BOX_MATCH_DECIMALS=3)`, skips
  unmatched boxes (warning), ignores classifications (warning), and writes only
  `DetectionEmbedding` rows: no detection, classification, occurrence, determination, null
  marker or calculated-field update.
- Regular pipelines: `create_detection_embeddings` runs after `create_detections` and before
  classifications, same matching key. Both write through `EmbeddingQuerySet.store`, which is
  insert-mostly: an identical vector (compared at half precision) is left alone, a different
  one is deleted and inserted, a row is never updated. Vectors with a non-finite value at half
  precision (NaN, infinity, beyond 65504) are skipped with a warning.
- `save_results` records the job on new detections, classifications and embeddings; the size
  filter, class masking and tracking record theirs on the classifications they add.

## The extract-features job

No new job type: an ordinary ML job (`MLJob`, key `ml`) whose pipeline is feature-only. Same
permission as any ML job. Scope is the job's capture set, deployment or single capture.
`filter_processed_images` delegates to `filter_images_missing_features`: an image is sent only
when a real detection on it lacks a `DetectionEmbedding` from one of the pipeline's algorithms
(`detections_missing_features`; classification vectors do not count). Both the image filter
and the request go through `embeddable_detections` (real box and known detector), so no image
is chosen without boxes to send. The async path also drops any task left with no boxes
(`_attach_detections_for_feature_pipeline` returns them), because a worker given an empty list
runs its own detector. The filter emits the same throttled `collect` heartbeat as regular
pipelines (`_CollectHeartbeat`). The project flag `reprocess_all_images` sends every real
detection again.

## Read path

`ami/main/models_future/embeddings.py`:
- `latest_vectors` / `vectors_for_detections(ids, algorithm_id, key="embedding")`: one UNION ALL
  query over embeddings and classification vectors, embedding preferred (the halfvec column is
  cast to `vector` so both sides share a type). Always one (algorithm, key); classification
  vectors count only for the `embedding` key.
  `vectors_for_detections` also keeps only the most common vector length, so an algorithm with
  both a 1024 embedding and a 2048 classification vector never mixes them.
- `cosine_similarity` (`ami/ml/post_processing/tracking_task.py`) raises on a shape mismatch.
- `algorithm_ids_with_vectors(**lookups)`: extractors with vectors for a set of detections.
- `feature_extractors_with_vectors(project, **lookups)`: per extractor, `embeddings_count`,
  `classification_vectors_count`, `is_default`; exposed as
  `GET /api/v2/events/{id}/feature-extractors/?project_id=` (`EventViewSet.feature_extractors`,
  `SessionFeatureExtractorSerializer`) for the tracking form.

## How tracking picks the extractor

`resolve_feature_algorithm(event, config)`:
1. `config.feature_extraction_algorithm_id` if given.
2. The only extractor with vectors in the session.
3. Several: `default_feature_algorithm_id(project, ids, source_image__event=event)`: the
   extractor with vectors for the most detections in the session (`detections_covered`, one
   query, either store counts once); a configured one (feature-extraction algorithm in a
   pipeline enabled for the project) wins if it covers at least
   `CONFIGURED_EXTRACTOR_MIN_COVERAGE` (0.9) of the best; ties go to the newest algorithm id.
   A half-finished backfill therefore never becomes the default. The run logs which one it compares.
   Gotcha: the Exists terms in `detections_covered` must be annotations, not a `Q` inside
   `Count(filter=...)`, or cachalot misses their tables and serves a stale count.
4. None: `require_features=True` skips the session; otherwise geometry-only matching.

Merge candidates use the same resolution over the two captures being compared.

## Tests

`ami/ml/test_feature_extraction.py` (feature-only save, dimension checks, extract scope, default
extractor, endpoint permissions and query count); `ami/ml/tests.py` `TestDetectionEmbeddings`
(regular-pipeline embeddings).
