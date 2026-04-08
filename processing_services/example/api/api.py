"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import logging

import fastapi

from .pipelines import (
    FlatBugDetectorPipeline,
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
from .utils import is_base64, is_url

# Configure root logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Get the root logger
logger = logging.getLogger(__name__)

app = fastapi.FastAPI()


pipelines: list[type[Pipeline]] = [
    FlatBugDetectorPipeline,
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

    source_images = [SourceImage(**img.model_dump()) for img in data.source_images]
    # Open source images once before processing
    for img in source_images:
        img.open(raise_exception=True)

    detections = create_detections(
        source_images=source_images,
        detection_requests=data.detections,
    )

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
    source_images: list[SourceImage],
    detection_requests: list[DetectionRequest] | None,
):
    if not detection_requests:
        return []

    # Group detection requests by source image id
    source_image_map = {img.id: img for img in source_images}
    grouped_detection_requests = {}
    for request in detection_requests:
        if request.source_image.id not in grouped_detection_requests:
            grouped_detection_requests[request.source_image.id] = []
        grouped_detection_requests[request.source_image.id].append(request)

    # Process each source image and its detection requests
    detections = []
    for source_image_id, requests in grouped_detection_requests.items():
        if source_image_id not in source_image_map:
            raise ValueError(
                f"A detection request for source image {source_image_id} was received, "
                "but no source image with that ID was provided."
            )

        logger.info(f"Processing existing detections for source image {source_image_id}.")

        for request in requests:
            source_image = source_image_map[source_image_id]
            cropped_image_id = (
                f"{source_image.id}-crop-{request.bbox.x1}-{request.bbox.y1}-{request.bbox.x2}-{request.bbox.y2}"
            )
            if not request.crop_image_url:
                logger.info("Detection request does not have a crop_image_url, crop the original source image.")
                assert source_image._pil is not None, "Source image must be opened before cropping."
                cropped_image_pil = source_image._pil.crop(
                    (request.bbox.x1, request.bbox.y1, request.bbox.x2, request.bbox.y2)
                )
            else:
                try:
                    logger.info(f"Opening existing cropped image from {request.crop_image_url}.")
                    if is_url(request.crop_image_url):
                        cropped_image = SourceImage(
                            id=cropped_image_id,
                            url=request.crop_image_url,
                        )
                    elif is_base64(request.crop_image_url):
                        logger.info("Decoding base64 cropped image.")
                        cropped_image = SourceImage(
                            id=cropped_image_id,
                            b64=request.crop_image_url,
                        )
                    else:
                        # Must be a filepath
                        cropped_image = SourceImage(
                            id=cropped_image_id,
                            filepath=request.crop_image_url,
                        )
                    cropped_image.open(raise_exception=True)
                    cropped_image_pil = cropped_image._pil
                except Exception as e:
                    logger.warning(f"Error opening cropped image: {e}")
                    logger.info(f"Falling back to cropping the original source image {source_image_id}.")
                    assert source_image._pil is not None, "Source image must be opened before cropping."
                    cropped_image_pil = source_image._pil.crop(
                        (request.bbox.x1, request.bbox.y1, request.bbox.x2, request.bbox.y2)
                    )

            # Create a Detection object
            det = Detection(
                source_image=SourceImage(
                    id=source_image.id,
                    url=source_image.url,
                ),
                bbox=request.bbox,
                id=cropped_image_id,
                url=request.crop_image_url or source_image.url,
                algorithm=request.algorithm,
            )
            # Set the _pil attribute to the cropped image
            det._pil = cropped_image_pil
            detections.append(det)
            logger.info(f"Created detection {det.id} for source image {source_image_id}.")

    return detections


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2000)
