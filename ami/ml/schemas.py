import datetime
import logging
import typing

import pydantic

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BoundingBox(pydantic.BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @classmethod
    def from_coords(cls, coords: list[float]) -> "BoundingBox":
        return cls(x1=coords[0], y1=coords[1], x2=coords[2], y2=coords[3])

    def to_string(self) -> str:
        return f"{self.x1},{self.y1},{self.x2},{self.y2}"

    def to_path(self) -> str:
        return "-".join([str(int(x)) for x in [self.x1, self.y1, self.x2, self.y2]])

    def to_tuple(self):
        return (self.x1, self.y1, self.x2, self.y2)


class AlgorithmReference(pydantic.BaseModel):
    name: str
    key: str


class AlgorithmCategoryMapResponse(pydantic.BaseModel):
    data: list[dict] = pydantic.Field(
        default_factory=dict,
        description="Complete data for each label, such as id, gbif_key, explicit index, source, etc.",
        examples=[
            [
                {"label": "Moth", "index": 0, "gbif_key": 1234},
                {"label": "Not a moth", "index": 1, "gbif_key": 5678},
            ]
        ],
    )
    labels: list[str] = pydantic.Field(
        default_factory=list,
        description="A simple list of string labels, in the correct index order used by the model.",
        examples=[["Moth", "Not a moth"]],
    )
    version: str | None = pydantic.Field(
        default=None,
        description="The version of the category map. Can be a descriptive string or a version number.",
        examples=["LepNet2021-with-2023-mods"],
    )
    description: str | None = pydantic.Field(
        default=None,
        description="A description of the category map used to train. e.g. source, purpose and modifications.",
        examples=["LepNet2021 with Schmidt 2023 corrections. Limited to species with > 1000 observations."],
    )
    uri: str | None = pydantic.Field(
        default=None,
        description="A URI to the category map file, could be a public web URL or object store path.",
    )


class AlgorithmConfigResponse(pydantic.BaseModel):
    name: str
    key: str = pydantic.Field(
        description=("A unique key for an algorithm to lookup the category map (class list) and other metadata."),
    )
    description: str | None = None
    task_type: str | None = pydantic.Field(
        default=None,
        description="The type of task the model is trained for. e.g. 'detection', 'classification', 'embedding', etc.",
        examples=["detection", "classification", "segmentation", "embedding"],
    )
    version: int = pydantic.Field(
        default=1,
        description="A sortable version number for the model. Increment this number when the model is updated.",
    )
    version_name: str | None = pydantic.Field(
        default=None,
        description="A complete version name e.g. '2021-01-01', 'LepNet2021'.",
    )
    uri: str | None = pydantic.Field(
        default=None,
        description="A URI to the weight or model details, could be a public web URL or object store path.",
    )
    category_map: AlgorithmCategoryMapResponse | None = None

    class Config:
        extra = "ignore"


class ClassificationResponse(pydantic.BaseModel):
    classification: str
    labels: list[str] | None = pydantic.Field(
        default=None,
        description=(
            "A list of all possible labels for the model, in the correct order. "
            "Omitted if the model has too many labels to include for each classification in the response. "
            "Use the category map from the algorithm to get the full list of labels and metadata."
        ),
    )
    scores: list[float] = []
    logits: list[float] | None = None
    inference_time: float | None = None
    algorithm: AlgorithmReference
    terminal: bool = True
    timestamp: datetime.datetime


class DetectionResponse(pydantic.BaseModel):
    source_image_id: str
    bbox: BoundingBox
    inference_time: float | None = None
    algorithm: AlgorithmReference
    timestamp: datetime.datetime
    crop_image_url: str | None = None
    classifications: list[ClassificationResponse] = []


class SourceImageRequest(pydantic.BaseModel):
    # @TODO bring over new SourceImage & b64 validation from the lepsAI repo
    id: str
    url: str
    # b64: str | None = None


class SourceImageResponse(pydantic.BaseModel):
    id: str
    url: str

    class Config:
        extra = "ignore"


KnownPipelineChoices = typing.Literal[
    "panama_moths_2023",
    "quebec_vermont_moths_2023",
    "uk_denmark_moths_2023",
]


class PipelineRequestConfigParameters(dict):
    """Parameters used to configure a pipeline request.

    Accepts any serializable key-value pair.
    Example: {"force_reprocess": True, "auth_token": "abc123"}

    Supported parameters are defined by the pipeline in the processing service
    and should be published in the Pipeline's info response.

    Parameters that are used by Antenna before sending the request to the Processing Service
    should be prefixed with "request_".
    Example: {"request_source_image_batch_size": 8}
    Such parameters need to be ignored by the schema in the Processing Service, or
    removed before sending the request to the Processing Service.
    """

    pass


class PipelineRequest(pydantic.BaseModel):
    pipeline: str
    source_images: list[SourceImageRequest]
    config: PipelineRequestConfigParameters | dict | None = None


class PipelineResultsResponse(pydantic.BaseModel):
    # pipeline: PipelineChoice
    pipeline: str
    algorithms: dict[str, AlgorithmConfigResponse] = pydantic.Field(
        default_factory=dict,
        description="A dictionary of all algorithms used in the pipeline, including their class list and other "
        "metadata, keyed by the algorithm key.",
    )
    total_time: float
    source_images: list[SourceImageResponse]
    detections: list[DetectionResponse]
    errors: list | str | None = None


class PipelineStageParam(pydantic.BaseModel):
    """A configurable parameter of a stage of a pipeline."""

    name: str
    key: str
    category: str = "default"


class PipelineStage(pydantic.BaseModel):
    """A configurable stage of a pipeline."""

    key: str
    name: str
    params: list[PipelineStageParam] = []
    description: str | None = None


class PipelineConfig(pydantic.BaseModel):
    """A configurable pipeline."""

    name: str
    slug: str
    version: int
    description: str | None = None
    algorithms: list[AlgorithmConfigResponse] = []
    stages: list[PipelineStage] = []


class ProcessingServiceInfoResponse(pydantic.BaseModel):
    """
    Information about the processing service returned from the Processing Service backend.
    """

    name: str
    description: str | None = None
    pipelines: list[PipelineConfig] = []
    algorithms: list[AlgorithmConfigResponse] = []


class ProcessingServiceStatusResponse(pydantic.BaseModel):
    """
    Status response returned by the Antenna API about the Processing Service.
    """

    timestamp: datetime.datetime
    request_successful: bool
    pipeline_configs: list[PipelineConfig] = []
    error: str | None = None
    server_live: bool | None = None
    pipelines_online: list[str] = []
    endpoint_url: str
    latency: float


class PipelineRegistrationResponse(pydantic.BaseModel):
    timestamp: datetime.datetime
    success: bool
    error: str | None = None
    pipelines: list[PipelineConfig] = []
    pipelines_created: list[str] = []
    algorithms_created: list[str] = []
