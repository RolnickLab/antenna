"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import logging
import time

import fastapi

from .algorithms import ALGORITHM_CHOICES
from .pipelines import ConstantPipeline, RandomPipeline
from .schemas import (
    AlgorithmConfig,
    PipelineConfig,
    PipelineRequest,
    PipelineResponse,
    ProcessingServiceInfoResponse,
    SourceImage,
    SourceImageResponse,
)

logger = logging.getLogger(__name__)

app = fastapi.FastAPI()

pipeline1 = PipelineConfig(
    name="ML Random Pipeline",
    slug="random",
    version=1,
    algorithms=[
        AlgorithmConfig(name="Random Detector", key="random_detector"),
        AlgorithmConfig(name="Always Moth Classifier", key="always_moth_classifier"),
    ],
)

pipeline2 = PipelineConfig(
    name="ML Constant Pipeline",
    slug="constant",
    description="A pipeline that always return a detection in the same position.",
    version=1,
    algorithms=[
        AlgorithmConfig(name="Constant Detector", key="constant_detector"),
        AlgorithmConfig(name="Always Moth Classifier", key="always_moth_classifier"),
    ],
)

pipelines = [pipeline1, pipeline2]
# Unique list of algorithms used in all pipelines:
algorithms_by_key = {algorithm.key: algorithm for pipeline in pipelines for algorithm in pipeline.algorithms}
algorithms = list(algorithms_by_key.values())


@app.get("/")
async def root():
    return fastapi.responses.RedirectResponse("/docs")


@app.get("/info", tags=["services"])
async def info() -> ProcessingServiceInfoResponse:
    info = ProcessingServiceInfoResponse(
        name="ML Backend Example",
        description="A template for a machine learning backend service.",
        pipelines=pipelines,
        algorithms=algorithms,
    )
    return info


# Check if the server is online
@app.get("/livez", tags=["health checks"])
async def livez():
    return fastapi.responses.JSONResponse(status_code=200, content={"status": True})


# Check if the pipelines are ready to process data
@app.get("/readyz", tags=["health checks"])
async def readyz():
    if pipelines:
        return fastapi.responses.JSONResponse(
            status_code=200, content={"status": [pipeline.slug for pipeline in pipelines]}
        )
    else:
        return fastapi.responses.JSONResponse(status_code=503, content={"status": "pipelines unavailable"})


@app.post("/process", tags=["services"])
async def process(data: PipelineRequest) -> PipelineResponse:
    pipeline_slug = data.pipeline

    source_image_results = [SourceImageResponse(**image.model_dump()) for image in data.source_images]
    source_images = [SourceImage(**image.model_dump()) for image in data.source_images]

    start_time = time.time()

    if pipeline_slug == "constant":
        pipeline = ConstantPipeline(source_images=source_images)  # returns same detections
    else:
        pipeline = RandomPipeline(source_images=source_images)  # returns random detections

    try:
        results = pipeline.run()
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        raise fastapi.HTTPException(status_code=422, detail=f"{e}")

    end_time = time.time()
    seconds_elapsed = float(end_time - start_time)

    response = PipelineResponse(
        pipeline=data.pipeline,
        algorithms=ALGORITHM_CHOICES,
        source_images=source_image_results,
        detections=results,
        total_time=seconds_elapsed,
    )
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2000)
