"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import logging
import time

import fastapi

from .pipeline import ConstantPipeline, DummyPipeline
from .schemas import (
    AlgorithmConfig,
    PipelineConfig,
    PipelineRequest,
    PipelineResponse,
    SourceImage,
    SourceImageResponse,
)

logger = logging.getLogger(__name__)

app = fastapi.FastAPI()

pipeline1 = PipelineConfig(
    name="ML Dummy Pipeline",
    slug="dummy",
    version=1,
    algorithms=[
        AlgorithmConfig(name="Dummy Detector", key="1"),
        AlgorithmConfig(name="Random Detector", key="2"),
        AlgorithmConfig(name="Always Moth Classifier", key="3"),
    ],
)

pipeline2 = PipelineConfig(
    name="ML Constant Pipeline",
    slug="constant",
    version=1,
    algorithms=[
        AlgorithmConfig(name="Dummy Detector", key="1"),
        AlgorithmConfig(name="Random Detector", key="2"),
        AlgorithmConfig(name="Always Moth Classifier", key="3"),
    ],
)

pipelines = [pipeline1, pipeline2]


@app.get("/")
async def root():
    return fastapi.responses.RedirectResponse("/docs")


@app.get("/info", tags=["services"])
async def info() -> list[PipelineConfig]:
    return pipelines


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


@app.post("/process_images", tags=["services"])
async def process(data: PipelineRequest) -> PipelineResponse:
    pipeline_slug = data.pipeline

    source_image_results = [SourceImageResponse(**image.model_dump()) for image in data.source_images]
    source_images = [SourceImage(**image.model_dump()) for image in data.source_images]

    start_time = time.time()

    if pipeline_slug == "constant":
        pipeline = ConstantPipeline(source_images=source_images)  # returns same detections
    else:
        pipeline = DummyPipeline(source_images=source_images)  # returns random detections

    try:
        results = pipeline.run()
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        raise fastapi.HTTPException(status_code=422, detail=f"{e}")

    end_time = time.time()
    seconds_elapsed = float(end_time - start_time)

    response = PipelineResponse(
        pipeline=data.pipeline,
        source_images=source_image_results,
        detections=results,
        total_time=seconds_elapsed,
    )
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2000)
