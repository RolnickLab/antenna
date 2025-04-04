# Set-Up Custom ML Backends and Models

## Questions for Michael
- TODO: Update `processing_services/example/api/test.py` -- maybe test the Local Pipeline with ViT?

## Environment Set Up

1. Add to the `example` processing_services app
2. Update `processing_services/example/requirements.txt`
3. Make sure the ml_backend service uses the example directory in `docker-compose.yml`
4. Install dependencies if required: `docker compose build ml_backend` and `docker compose up -d ml_backend`

## Add Algorithms, Pipelines, and ML Backend/Processing Services

1. Define algorithms in `processing_services/example/api/algorithms.py`.
    - Each algorithm has a `compile()` and `run()` function.
    - Make sure to update `algorithm_config_response`.
2. Define a custom pipeline in `processing_services/example/api/pipelines.py`
    Implement/Update:
    - `config`
    - `stages` (a series of algorithms)
    - `make_detections` (call `run()` for each algorithm and process the outputs of each stage/algorithm accordingly)
        - must return a `list[DetectionResponse]`
3. Add the custom pipeline to `processing_services/example/api/api.py`
```
from .pipelines import ConstantDetectorClassification, CustomPipeline, Pipeline

...

pipelines: list[type[Pipeline]] = [CustomPipeline, ConstantDetectorClassification]

...

```
4. Update `PipelineChoice` in `processing_services/example/api/schemas.py` to include the key of the new pipeline.
```
PipelineChoice = typing.Literal["random", "constant", "local-pipeline", "constant-detector-classifier-pipeline"]
```
