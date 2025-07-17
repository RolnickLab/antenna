"""
Fast API interface for processing images through the localization and classification pipelines.
"""

import logging

import fastapi

from .processing import get_pipeline_info, process_pipeline_request
from .schemas import PipelineRequest, PipelineResultsResponse, ProcessingServiceInfoResponse

logger = logging.getLogger(__name__)

app = fastapi.FastAPI()


@app.get("/")
async def root():
    return fastapi.responses.RedirectResponse("/docs")


@app.get("/info", tags=["services"])
async def info() -> ProcessingServiceInfoResponse:
    pipelines = get_pipeline_info()
    info = ProcessingServiceInfoResponse(
        name="ML Backend Template",
        description=(
            "A template for an inference API that allows the user to run different sequences of machine learning "
            "models and processing methods on images for the Antenna platform."
        ),
        pipelines=[pipeline.config for pipeline in pipelines],
        # algorithms=list(get_algorithm_choices().values()),
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
    pipelines = get_pipeline_info()
    pipeline_slugs = [pipeline.config.slug for pipeline in pipelines]
    if pipeline_slugs:
        return fastapi.responses.JSONResponse(status_code=200, content={"status": pipeline_slugs})
    else:
        return fastapi.responses.JSONResponse(status_code=503, content={"status": []})


@app.post("/process", tags=["services"])
async def process(data: PipelineRequest) -> PipelineResultsResponse:
    try:
        response = process_pipeline_request(data)
        return response
    except ValueError as e:
        raise fastapi.HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing pipeline: {e}")
        raise fastapi.HTTPException(status_code=500, detail=f"Internal server error: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=2000)
