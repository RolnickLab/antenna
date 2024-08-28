"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import time

import fastapi

from .pipeline import DummyPipeline
from .schemas import PipelineRequest, PipelineResponse, SourceImage, SourceImageResponse

app = fastapi.FastAPI()


@app.get("/")
async def root():
    return fastapi.responses.RedirectResponse("/docs")


@app.post("/pipeline/process")
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
