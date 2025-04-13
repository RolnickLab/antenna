# Set-Up Custom ML Backends and Models

## Background

A processing service or ML backend is a group of pipelines used to process images. In real life, the ML backend can be hosted on a separate server where it handles processing the source images, compiling the models, and running inference.

In this directory, we define locally-run processing services as FastAPI apps. A basic ML backend has the following endpoints:
- `/info`: returns data about what pipelines and algorithms are supported by the service.
- `/livez`
- `/readyz`
- `/process`: receives source images via a `PipelineRequest` and returns a `PipelineResponse` containing detections

`processing_services` contains 2 apps:
- `example`: demos how to add custom pipelines/algorithms.
- `minimal`: a simple ML backend for basic testing of the processing service API. This minimal app also runs within the main Antenna docker compose stack.

If your goal is to run an ML backend locally, simply copy the `example` directory and follow the steps below.

## Environment Set Up

1. Update `processing_services/example/requirements.txt` with required packages (i.e. PyTorch, etc)
2. Rebuild container to install updated dependencies. Start the minimal and example ML backends: `docker compose -f processing_services/docker-compose.yml up -d --build ml_backend_example`
3. To test that everything works, register a new processing service in Antenna with endpoint URL http://ml_backend_example:2000. All ML backends are connected to the main docker compose stack using the `ml_network`.


## Add Algorithms, Pipelines, and ML Backend/Processing Services

1. Define algorithms in `processing_services/example/api/algorithms.py`.
    - Each algorithm has a `compile()` and `run()` function.
    - Make sure to update `algorithm_config_response`.
2. Define a new pipeline class (i.e. `NewPipeline`) in `processing_services/example/api/pipelines.py`
    Implement/Update:
    - `stages` (a list of algorithms in order of execution -- typically `stages = [Localizer(), Classifier()]`)
    - `batch_size` (a list of integers representing the number of entities that can be processed at a time by each stage -- i.e. [1, 1] means that the localizer can process 1 source image a time and the classifier can process 1 bounding box/detection at a time)
    - `config`
3. As needed, override the default `run()` function. Some important considerations:
    - Always run `_get_pipeline_response` at the end of `run()` to get a valid `PipelineResultsResponse`
    - Typically, each algorithm in a pipeline has its own stage. Each stage handles batchifying inputs and running the algorithm.
    - Each stage should have the decorator `@pipeline_stage(stage_index=INT, error_type=ERROR_TYPE)`. The `stage_index` represents the stage's position in the order of stages. Each stage is wrapped in a try-except block and raises `ERROR_TYPE` on failure.
    - Examples:
        - `ConstantDetectionPipeline`: localizer + classifier
        - `ZeroShotobjectDetectorPipeline`: detector
        - `FlatBugDetectorPipeline`: localizer

4. Add `NewPipeline` to `processing_services/example/api/api.py`

```
from .pipelines import ConstantDetectionPipeline, FlatBugDetectorPipeline, Pipeline, ZeroShotObjectDetectorPipeline, NewPipeline

...

pipelines: list[type[Pipeline]] = [ConstantDetectionPipeline, FlatBugDetectorPipeline, ZeroShotObjectDetectorPipeline, NewPipeline ]

...

```
5. Update `PipelineChoice` in `processing_services/example/api/schemas.py` to include the slug of the new pipeline, as defined in `NewPipeline`'s config.

```
PipelineChoice = typing.Literal[
    "constant-detection-pipeline", "flat-bug-detector-pipeline", "zero-shot-object-detector-pipeline", "new-pipeline"
]
```
