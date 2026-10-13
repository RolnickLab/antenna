# Set-Up Custom ML Backends and Models

## Background

A processing service or ML backend is a group of pipelines used to process images. In real life, the ML backend can be hosted on a separate server where it handles processing the source images, compiling the models, and running inference.

In this directory, we define locally-run processing services as FastAPI apps. A basic ML backend has the following endpoints:
- `/info`: returns data about what pipelines and algorithms are supported by the service.
- `/livez`
- `/readyz`
- `/process`: receives source images and existing detections via a `PipelineRequest` and returns a `PipelineResponse` containing detections

`processing_services` contains 2 apps:
- `example`: demos how to add custom pipelines/algorithms.
- `minimal`: a simple ML backend for basic testing of the processing service API. This minimal app also runs within the main Antenna docker compose stack.

If your goal is to run an ML backend locally, simply copy the `example` app and follow the steps below.

## v1 vs v2 processing services

Antenna supports two processing-service paradigms:

- **v1 (push / synchronous):** the service exposes `/info`, `/livez`, `/readyz`, `/process`. Antenna POSTs a `PipelineRequest` to `/process` when a job runs. Good for interactive/playground requests on a single image and for exposing pipeline schema at `/api/v2/docs/`.
- **v2 (pull / async / worker):** a worker polls Antenna's job-queue HTTP endpoints (`POST /api/v2/jobs/{id}/tasks/`, `POST /api/v2/jobs/{id}/result/`) and processes tasks queued by Antenna in NATS JetStream. Antenna proxies NATS internally so the worker only talks HTTP. Good for long-running workloads, firewall-isolated GPU fleets, and horizontal scaling.

The `minimal` container supports **both modes** and is driven by a `MODE` env var:

- `MODE=api` (default; what CI uses) — v1 FastAPI only.
- `MODE=worker` — v2 worker poll loop only.
- `MODE=api+worker` — both, in one container. Used by `processing_services/docker-compose.yml` for local dev. Exercises the real v2 pull path (Redis / NATS / Celery / Celery Beat) with lightweight stub pipelines, no ML dependencies.

See `docs/claude/planning/2026-04-17-minimal-worker-design.md` for the design.

### Running the v2 path locally

```bash
docker compose up -d                                             # Antenna core
docker compose -f processing_services/docker-compose.yml up -d   # minimal container in api+worker mode
```

The minimal container self-registers a `ProcessingService` (no `endpoint_url`, async-mode) against the "Default Project" seeded by `ami/main/management/commands/ensure_default_project.py`. Submit an `async_api` job for the `constant` or `random-detection-random-species` pipeline and the worker picks it up.

### What a pull-mode worker must do

These rules come from Antenna's job API, and the AMI Data Companion's worker follows them too:

- Authenticate with `Authorization: Token <token>`.
- Find work with one call for all of its pipelines: `GET /api/v2/jobs/?pipeline__slug__in=<slugs>&ids_only=1&incomplete_only=1&dispatch_mode=async_api`. Each listed job carries its `pipeline_slug`. Antenna treats this call as the worker's heartbeat, so a service that stops polling shows as offline after about a minute.
- Reserve tasks with `POST /api/v2/jobs/{id}/tasks/` and return one result per task to `POST /api/v2/jobs/{id}/result/`, carrying the task's `reply_subject`. Include the task's image in the result's `source_images` even when nothing was detected, because that is how Antenna counts the image as processed. A failure is reported as `{"error": "...", "image_id": "..."}` so the task is still acknowledged.
- Register the pipelines it serves with `POST /api/v2/projects/{id}/pipelines/`, listing every algorithm its results can name.
- Expect `503` from either endpoint when Antenna's queue is briefly unavailable, and retry.

The CI job `test-async-processing-service` runs `scripts/ci/async_processing_service_e2e.sh`, which runs an `async_api` job through the minimal worker end to end.


## Environment Set Up

1. Update `processing_services/example/requirements.txt` with required packages (i.e. PyTorch, etc)
2. Rebuild container to install updated dependencies. Start the minimal and example ML backends: `docker compose -f processing_services/docker-compose.yml up -d --build ml_backend_example`
3. To test that everything works, register a new processing service in Antenna with endpoint URL http://ml_backend_example:2000. All ML backends are connected to the main docker compose stack using the `antenna_network`.


## Add Algorithms, Pipelines, and ML Backend/Processing Services

1. Define algorithms in `processing_services/example/api/algorithms.py`.
    - Each algorithm has a `compile()` and `run()` function.
    - Make sure to update `algorithm_config_response`.
    - `compile()` function should handle loading the saved model from cache
2. Define a new pipeline class (i.e. `NewPipeline`) in `processing_services/example/api/pipelines.py`
    Implement/Update:
    - `stages` (a list of algorithms in order of execution -- typically `stages = [Localizer(), Classifier()]`)
        - For dynamic loading of stages, which is useful for passing the pipeline request's `config`, implement `get_stages()`. A good example of this is in the `ZeroShotObjectDetectorPipeline` class.
    - `batch_size` (a list of integers representing the number of entities that can be processed at a time by each stage -- i.e. [1, 1] means that the localizer can process 1 source image a time and the classifier can process 1 bounding box/detection at a time)
    - `config`
3. Implement the `run()` function. Some important considerations:
    - Always run `_get_pipeline_response` at the end of `run()` to get a valid `PipelineResultsResponse`
    - Each algorithm/stage in a pipeline should take a list of `SourceImage`s or `Detection`s and produce a list of `Detection`s (with or without classifications). The class member function `_get_detections()` handles this general stage structure; it batchifys the inputs and produces output detections.
    - 4 example pipelines are already implemented. See the table at the end of the README for examples of what detections from each pipeline look like.
        - `ZeroShotHFClassifierPipeline`
        - `ZeroShotObjectDetectorPipeline`
        - `ZeroShotObjectDetectorWithRandomSpeciesClassifierPipeline`
        - `ZeroShotObjectDetectorWithConstantClassifierPipeline`

4. Add `NewPipeline` to `processing_services/example/api/api.py`

```
from .pipelines import (
    Pipeline,
    ZeroShotHFClassifierPipeline,
    ZeroShotObjectDetectorPipeline,
    ZeroShotObjectDetectorWithConstantClassifierPipeline,
    ZeroShotObjectDetectorWithRandomSpeciesClassifierPipeline,
    NewPipeline
)
...

pipelines: list[type[Pipeline]] = [
    ZeroShotHFClassifierPipeline,
    ZeroShotObjectDetectorPipeline,
    ZeroShotObjectDetectorWithConstantClassifierPipeline,
    ZeroShotObjectDetectorWithRandomSpeciesClassifierPipeline,
    NewPipeline,
]
```
5. Update `PipelineChoice` in `processing_services/example/api/schemas.py` to include the slug of the new pipeline, as defined in `NewPipeline`'s config.

```
PipelineChoice = typing.Literal[
    "zero-shot-hf-classifier-pipeline",
    "zero-shot-object-detector-pipeline",
    "zero-shot-object-detector-with-constant-classifier-pipeline",
    "zero-shot-object-detector-with-random-species-classifier-pipeline",
    "new-pipeline-slug",
]
```
## Demo

## `minimal` Pipelines and Output Images

- `ConstantPipeline` and `RandomDetectionRandomSpeciesPipeline`
![MinimalReprocessing](images/MinimalReprocessing.png)


## `example` Pipelines and Output Images

- `ZeroShotHFClassifierPipeline`
![ZeroShotHFClassifierPipeline](images/ZeroShotHFClassifierPipeline.png)

- `ZeroShotObjectDetectorWithRandomSpeciesClassifierPipeline` and `ZeroShotObjectDetectorWithConstantClassifierPipeline` (using reprocessing, skips the Zero Shot Object Detector if there are existing detections)
![ZeroShotReprocessing](images/ZeroShotReprocessing.png)
