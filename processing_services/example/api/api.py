"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import logging
import time

import fastapi

from .pipelines import ConstantDetectorClassification, CustomPipeline, Pipeline
from .schemas import (
    AlgorithmConfigResponse,
    PipelineRequest,
    PipelineResultsResponse,
    ProcessingServiceInfoResponse,
    SourceImage,
    SourceImageResponse,
)

# Configure root logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Get the root logger
logger = logging.getLogger(__name__)

app = fastapi.FastAPI()


pipelines: list[type[Pipeline]] = [CustomPipeline, ConstantDetectorClassification]
pipeline_choices: dict[str, type[Pipeline]] = {pipeline.config.slug: pipeline for pipeline in pipelines}
algorithm_choices: dict[str, AlgorithmConfigResponse] = {
    algorithm.key: algorithm for pipeline in pipelines for algorithm in pipeline.config.algorithms
}


@app.get("/")
async def root():
    return fastapi.responses.RedirectResponse("/docs")


@app.get("/info", tags=["services"])
async def info() -> ProcessingServiceInfoResponse:
    info = ProcessingServiceInfoResponse(
        name="Custom ML Backend",
        description=("A template for running custom models locally."),
        pipelines=[pipeline.config for pipeline in pipelines],
        # algorithms=list(algorithm_choices.values()),
    )
    return info


# Check if the server is online
@app.get("/livez", tags=["health checks"])
async def livez():
    return fastapi.responses.JSONResponse(status_code=200, content={"status": True})


# Check if the pipelines are ready to process data
@app.get("/readyz", tags=["health checks"])
async def readyz():
    """
    Check if the server is ready to process data.

    Returns a list of pipeline slugs that are online and ready to process data.
    @TODO may need to simplify this to just return True/False. Pipeline algorithms will likely be loaded into memory
    on-demand when the pipeline is selected.
    """
    if pipeline_choices:
        return fastapi.responses.JSONResponse(status_code=200, content={"status": list(pipeline_choices.keys())})
    else:
        return fastapi.responses.JSONResponse(status_code=503, content={"status": []})


@app.post("/process", tags=["services"])
async def process(data: PipelineRequest) -> PipelineResultsResponse:
    pipeline_slug = data.pipeline

    source_images = [SourceImage(**image.model_dump()) for image in data.source_images]
    source_image_results = [SourceImageResponse(**image.model_dump()) for image in data.source_images]

    start_time = time.time()

    try:
        Pipeline = pipeline_choices[pipeline_slug]
    except KeyError:
        raise fastapi.HTTPException(status_code=422, detail=f"Invalid pipeline choice: {pipeline_slug}")

    pipeline = Pipeline(source_images=source_images)
    try:
        results = pipeline.run()
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        raise fastapi.HTTPException(status_code=422, detail=f"{e}")

    end_time = time.time()
    seconds_elapsed = float(end_time - start_time)

    response = PipelineResultsResponse(
        pipeline=pipeline_slug,
        algorithms={algorithm.key: algorithm for algorithm in pipeline.config.algorithms},
        source_images=source_image_results,
        detections=results,
        total_time=seconds_elapsed,
    )
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2000)
