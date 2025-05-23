"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import logging

import fastapi

from .pipelines import (
    Pipeline,
    ZeroShotHFClassifierPipeline,
    ZeroShotObjectDetectorPipeline,
    ZeroShotObjectDetectorWithConstantClassifierPipeline,
    ZeroShotObjectDetectorWithRandomSpeciesClassifierPipeline,
)
from .schemas import (
    AlgorithmConfigResponse,
    Detection,
    DetectionRequest,
    PipelineRequest,
    PipelineRequestConfigParameters,
    PipelineResultsResponse,
    ProcessingServiceInfoResponse,
    SourceImage,
)

# Configure root logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Get the root logger
logger = logging.getLogger(__name__)

app = fastapi.FastAPI()


pipelines: list[type[Pipeline]] = [
    ZeroShotHFClassifierPipeline,
    ZeroShotObjectDetectorPipeline,
    ZeroShotObjectDetectorWithConstantClassifierPipeline,
    ZeroShotObjectDetectorWithRandomSpeciesClassifierPipeline,
]
pipeline_choices: dict[str, type[Pipeline]] = {pipeline.config.slug: pipeline for pipeline in pipelines}
algorithm_choices: dict[str, AlgorithmConfigResponse] = {
    algorithm.key: algorithm for pipeline in pipelines for algorithm in pipeline.config.algorithms
}

# -----------
# API endpoints
# -----------


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
    request_config = data.config

    detections = create_detections(
        detection_requests=data.detections,
    )
    source_images = [SourceImage(**image.model_dump()) for image in data.source_images]

    try:
        Pipeline = pipeline_choices[pipeline_slug]
    except KeyError:
        raise fastapi.HTTPException(status_code=422, detail=f"Invalid pipeline choice: {pipeline_slug}")

    pipeline_request_config = PipelineRequestConfigParameters(**dict(request_config)) if request_config else {}
    try:
        pipeline = Pipeline(
            source_images=source_images,
            request_config=pipeline_request_config,
            existing_detections=detections,
        )
        pipeline.compile()
    except Exception as e:
        logger.error(f"Error compiling pipeline: {e}")
        raise fastapi.HTTPException(status_code=422, detail=f"{e}")

    try:
        response = pipeline.run()
    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        raise fastapi.HTTPException(status_code=422, detail=f"{e}")

    return response


# -----------
# Helper functions
# -----------


def create_detections(
    detection_requests: list[DetectionRequest] | None,
):
    detections = (
        [
            Detection(
                source_image=SourceImage(
                    id=detection.source_image.id,
                    url=detection.source_image.url,
                ),
                bbox=detection.bbox,
                id=(
                    f"{detection.source_image.id}-crop-"
                    f"{detection.bbox.x1}-{detection.bbox.y1}-"
                    f"{detection.bbox.x2}-{detection.bbox.y2}"
                ),
                url=detection.crop_image_url,
                algorithm=detection.algorithm,
            )
            for detection in detection_requests
        ]
        if detection_requests
        else []
    )

    return detections


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2000)
