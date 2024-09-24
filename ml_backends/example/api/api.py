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

# Make slash and no slash endpoints work:


@app.get("/")
async def root():
    return fastapi.responses.RedirectResponse("/docs")


# @app.get("/info/{model_name}")
# async def get_model_info(model_name: str):
#     if p in pipelines:
#         return models[model_name]
#     else:
#         raise Exception("Model not found")


@app.get("/info")
async def info() -> list[PipelineConfig]:
    return pipelines


# Check if the server online & ready to process data -- @TODO: /livez, /readyz
@app.get("/healthcheck")
async def healthcheck():
    return "OK"


@app.post("/pipeline/process/")  # @TODO: Future change use @app.post("/{pipeline_name}/process/")
async def process(data: PipelineRequest) -> PipelineResponse:
    source_image_results = [SourceImageResponse(**image.model_dump()) for image in data.source_images]
    source_images = [SourceImage(**image.model_dump()) for image in data.source_images]

    start_time = time.time()

    pipeline = DummyPipeline(source_images=source_images)
    results = pipeline.run()

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
