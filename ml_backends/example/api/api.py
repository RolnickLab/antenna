"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import time

import fastapi

from .pipeline import DummyPipeline
from .schemas import (
    PipelineConfig,
    PipelineRequest,
    PipelineResponse,
    PipelineStage,
    PipelineStageParam,
    SourceImage,
    SourceImageResponse,
)

app = fastapi.FastAPI()

pipeline = PipelineConfig(
    name="Pipeline 1",
    slug="pipeline1",
    stages=[
        PipelineStage(
            name="Stage 1",
            key="stage1",
            params=[PipelineStageParam(name="Panama Moths", key="panama", category="Classifier")],
        )
    ],
)

pipelines = [pipeline]


@app.get("/")
async def root():
    return fastapi.responses.RedirectResponse("/docs")


@app.get("/info", tags=["services"])
async def info() -> list[PipelineConfig]:
    return pipelines


# Check if the server is online
@app.get("/livez", tags=["health checks"])
async def livez():
    return fastapi.responses.JSONResponse(status_code=200, content={"status": "ok"})


# Check if the server is ready to process data
@app.get("/readyz", tags=["health checks"])
async def readyz():
    if pipelines:
        return fastapi.responses.JSONResponse(status_code=200, content={"status": "ok"})
    else:
        return fastapi.responses.JSONResponse(status_code=503, content={"status": "pipelines unavailable"})


@app.post("/pipeline/process", tags=["services"])  # @TODO: Future change use @app.post("/{pipeline_name}/process/")
async def process(data: PipelineRequest) -> PipelineResponse:
    source_image_results = [SourceImageResponse(**image.model_dump()) for image in data.source_images]
    source_images = [SourceImage(**image.model_dump()) for image in data.source_images]

    start_time = time.time()

    pipeline = DummyPipeline(source_images=source_images)
    try:
        results = pipeline.run()
    except Exception as e:
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
