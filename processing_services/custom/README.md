# Set-Up Custom ML Backends and Models

## Questions for Michael
- Class attributes should be at top or bottom of class definition? see pipelines.py
- Why do I get issues when i try to make a separate compose and just modify this service? the image wouldn't build properly or the right docker file wasn't being used...transformers wasn't installed

## Environment Set Up

1. Add to the `custom` processing_services app
2. Update `processing_services/custom/requirements.txt`
3. Make sure the ml_backend service uses the custom directory in `docker-compose.yml`
4. Install dependencies if required: `docker compose build ml_backend` and `docker compose up -d ml_backend`

## Add Algorithms, Pipelines, and ML Backend/Processing Services

1. Define algorithms in `processing_services/custom/api/algorithms.py`.
    - Each algorithm has a `compile()` and `run()` function.
    - Make sure to update `algorithm_config_response`.
2. Define a custom pipeline in `processing_services/custom/api/pipelines.py`
    Implement/Update:
    - `config`
    - `stages` (a series of algorithms)
    - `make_detections` (call `run()` for each algorithm and process the outputs of each stage/algorithm accordingly)
        - must return a `list[DetectionResponse]`
3. Add the custom pipeline to `processing_services/custom/api/api.py`
```
from .pipelines import ConstantDetectorClassification, CustomPipeline, Pipeline

...

pipelines: list[type[Pipeline]] = [CustomPipeline, ConstantDetectorClassification]

...

```
4. Update `PipelineChoise` in `processing_services/custom/api/schemas.py` to include the key of the new pipeline.
```
PipelineChoice = typing.Literal["random", "constant", "local-pipeline", "constant-detector-classifier-pipeline"]
```
