"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import datetime
import inspect
import logging
import os
import pathlib

import fastapi
import pydantic
import requests

from .pipelines import (
    BioCLIP25LogRegPipeline,
    BioCLIPPanamaPipeline,
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
from . import algorithms, training
from .utils import is_base64, is_url

# Configure root logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Get the root logger
logger = logging.getLogger(__name__)

# Where retrained heads are written. Kept off the model cache so a training run
# cannot overwrite the head the service is currently serving.
TRAINED_HEADS_DIR = os.environ.get("BIOCLIP_TRAINED_HEADS_DIR", "/data/bioclip-service/trained_heads")

app = fastapi.FastAPI()


pipelines: list[type[Pipeline]] = [
    BioCLIP25LogRegPipeline,
    BioCLIPPanamaPipeline,
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
        name="BioCLIP ML Backend",
        description=("BioCLIP 2.5 with a logistic-regression classification head."),
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


class TrainRequest(pydantic.BaseModel):
    """Retrain a classifier head from a dataset Antenna has already prepared."""

    dataset_url: str = pydantic.Field(
        description="URL of the npz training set Antenna wrote to storage."
    )
    algorithm_key: str = pydantic.Field(
        description="Which head to retrain. Its current weights are the baseline the new head must beat."
    )
    job_id: int | None = pydantic.Field(
        default=None,
        description="Antenna job to report back to. Without it the result is only returned in this response.",
    )
    callback_url: str | None = pydantic.Field(
        default=None,
        description="Where to post the result when training finishes.",
    )
    callback_token: str | None = pydantic.Field(
        default=None,
        description="Token for the callback, so Antenna can tell a real result from a forged one.",
    )
    name: str | None = pydantic.Field(default=None, description="Name for the produced head.")
    min_per_species: int = 2
    min_improvement: float = 0.0
    save: bool = pydantic.Field(
        default=True,
        description="Write the head to disk. It is never loaded into the running service automatically.",
    )


class TrainResponse(pydantic.BaseModel):
    promote: bool
    reason: str
    warnings: list[str]
    rows: dict
    counts: dict
    dropped_species: list[str]
    candidate_metrics: dict
    incumbent_metrics: dict | None
    labels: list[str]
    saved: dict[str, str] | None
    trained_at: str
    reported_to_antenna: bool = False


@app.post("/train", tags=["training"])
async def train(data: TrainRequest) -> TrainResponse:
    """
    Retrain a classifier head from human-verified labels.

    Antenna prepares the dataset and hands over a URL; this downloads it, fits a new head,
    and scores it against the head currently in service on the same held-out rows. It never
    swaps the running head: promoting is a separate, deliberate step, because an automatic
    swap would let one bad training run quietly degrade every later classification.
    """
    try:
        rows, dataset_metadata = training.fetch_dataset(data.dataset_url)
    except requests.HTTPError as e:
        raise fastapi.HTTPException(status_code=502, detail=f"Could not download the training set: {e}")
    except Exception as e:
        raise fastapi.HTTPException(status_code=422, detail=f"Could not read the training set: {e}")

    if not rows:
        raise fastapi.HTTPException(status_code=422, detail="The training set is empty.")

    incumbent = _incumbent_head(data.algorithm_key)

    try:
        result = training.retrain(
            rows=rows,
            incumbent=incumbent,
            min_per_species=data.min_per_species,
            min_improvement=data.min_improvement,
        )
    except training.NotEnoughData as e:
        raise fastapi.HTTPException(status_code=422, detail=str(e))

    saved = None
    if data.save:
        name = data.name or f"head-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        saved = training.save_head(result, pathlib.Path(TRAINED_HEADS_DIR), name)

    response = TrainResponse(
        promote=result["promote"],
        reason=result["reason"],
        warnings=result["warnings"],
        rows=result["rows"],
        counts=result["counts"],
        dropped_species=result["dropped_species"],
        candidate_metrics=result["candidate_metrics"],
        incumbent_metrics=result["incumbent_metrics"],
        labels=result["labels"],
        saved=saved,
        trained_at=result["trained_at"],
    )

    if data.callback_url:
        response.reported_to_antenna = _report_to_antenna(data, response, dataset_metadata)

    return response


def _report_to_antenna(data: TrainRequest, response: "TrainResponse", dataset_metadata: dict) -> bool:
    """
    Tell the Antenna job how the run went.

    Reported rather than raised on failure: the training itself succeeded, and losing the
    callback should not make the caller think it did not.
    """
    payload = {
        "job_id": data.job_id,
        "algorithm_key": data.algorithm_key,
        "dataset": dataset_metadata,
        "result": response.model_dump(),
    }
    headers = {"Content-Type": "application/json"}
    if data.callback_token:
        headers["Authorization"] = f"Token {data.callback_token}"
    try:
        reply = requests.post(data.callback_url, json=payload, headers=headers, timeout=60)
        reply.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Trained successfully but could not report to Antenna at {data.callback_url}: {e}")
        return False


def _incumbent_head(algorithm_key: str) -> dict | None:
    """
    Load the weights of the head currently in service, so a new head can be compared to it.

    Scans the algorithm classes rather than a pipeline's `stages`, because stages only
    exist once a pipeline is instantiated. Returns None when the key names no local head;
    the caller then refuses to promote rather than promoting something it could not compare.
    """
    for candidate in vars(algorithms).values():
        if not inspect.isclass(candidate) or not issubclass(candidate, algorithms.Algorithm):
            continue
        if not hasattr(candidate, "_load_head_arrays"):
            continue
        try:
            instance = candidate()
            if instance.algorithm_config_response.key != algorithm_key:
                continue
            weights, bias, classes = instance._load_head_arrays()
            # The npz's `classes` holds column indices, not names. The species names come
            # from the category map, so use that; otherwise every label comparison against
            # Antenna's taxon names silently finds nothing in common.
            labels = [str(label) for label in instance.get_category_map().labels]
            if len(labels) != weights.shape[0]:
                logger.warning(
                    f"{candidate.__name__}: category map has {len(labels)} labels but the head has "
                    f"{weights.shape[0]} outputs. Falling back to the names stored in the npz."
                )
                labels = [str(c) for c in classes]
        except Exception as e:
            logger.warning(f"Could not load the current head for {candidate.__name__}: {e}")
            continue
        return {"weights": weights, "bias": bias, "labels": labels}
    return None
