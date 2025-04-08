# Set-Up Custom ML Backends and Models

## Environment Set Up

1. All changes will be made in the `processing_services/example` app
2. Update `processing_services/example/requirements.txt` with required packages (i.e. PyTorch, etc)
3. Rebuild container to install updated dependencies. Start the minimal and example ml backends: `docker compose -f processing_services/docker-compose.yml up -d --build ml_backend_example`

## Add Algorithms, Pipelines, and ML Backend/Processing Services

1. Define algorithms in `processing_services/example/api/algorithms.py`.
    - Each algorithm has a `compile()` and `run()` function.
    - Make sure to update `algorithm_config_response`.
2. Define a new pipeline class (i.e. `NewPipeline`) in `processing_services/example/api/pipelines.py`
    Implement/Update:
    - `config`
    - `stages` (a list of algorithms in order of execution -- typically `stages = [Detector(), Classifier()]`)
3. OPTIONAL: Override the default `run()` function.
    - The `Pipeline` class defines a basic detector-classifier pipeline. Batch processing can be applied to images fed into the detector and/or detections fed into the classifier.
    - In general, the input/output types of `run()`, `get_detector_response()`, and `get_classifier_response()` should not change.
    - `make_detections` (call `run()` for each algorithm and process the outputs of each stage/algorithm accordingly)
        - must return a `list[DetectionResponse]`
3. Add `NewPipeline` to `processing_services/example/api/api.py`

```
from .pipelines import ConstantDetectorClassification, CustomPipeline, Pipeline, NewPipeline

...
pipelines: list[type[Pipeline]] = [CustomPipeline, ConstantDetectorClassification, NewPipeline ]

...

```
4. Update `PipelineChoice` in `processing_services/example/api/schemas.py` to include the slug of the new pipeline, as defined in `NewPipeline`'s config.

```
PipelineChoice = typing.Literal["random", "constant", "local-pipeline", "constant-detector-classifier-pipeline", "new-pipeline"]
```
