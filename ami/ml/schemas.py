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
    def from_coords(cls, coords: typing.Any, raise_on_error: bool = True) -> "BoundingBox | None":
        """
        Create BoundingBox from coordinate list [x1, y1, x2, y2].

        Args:
            coords: List of 4 float coordinates
            raise_on_error: If True (default), raises ValueError on invalid input.
                           If False, returns None on invalid input.
        """
        if not isinstance(coords, list) or len(coords) != 4:
            if raise_on_error:
                if not isinstance(coords, list):
                    raise ValueError(f"BoundingBox coords must be a list, got {type(coords).__name__}")
                raise ValueError(f"BoundingBox coords must have 4 elements, got {len(coords)}")
            return None
        try:
            return cls(x1=coords[0], y1=coords[1], x2=coords[2], y2=coords[3])
        except (TypeError, pydantic.ValidationError) as e:
            if raise_on_error:
                raise ValueError(f"Invalid BoundingBox coordinates: {e}") from e
            return None

    @property
    def width(self) -> float:
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> float:
        return abs(self.y2 - self.y1)

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


class AlgorithmTrainingConfig(pydantic.BaseModel):
    """
    How to retrain an algorithm. Declared by the processing service, editable afterwards.

    Split across two sides on purpose: Antenna reads the dataset settings when it builds
    the training set, and passes the rest to the service, which owns the fitting.
    """

    # Dataset settings, used by Antenna.
    min_per_species: int = pydantic.Field(
        default=2,
        description="Drop species with fewer verified crops than this. One example cannot be evaluated.",
    )
    test_fraction: float = pydantic.Field(default=0.2, description="Share of occurrences held out for evaluation.")
    split_salt: str = pydantic.Field(
        default="antenna-head-v1",
        description="Changing this reshuffles the held-out set, which makes old and new heads incomparable.",
    )

    # Fitting settings, used by the processing service.
    head_type: str = pydantic.Field(
        default="linear",
        description="Shape of the head to fit, e.g. 'linear' or 'mlp1'.",
        examples=["linear", "mlp1"],
    )
    epochs: int = 300
    learning_rate: float = 0.01
    weight_decay: float = 1e-4
    min_improvement: float = pydantic.Field(
        default=0.0,
        description="A new head must beat the current one by more than this to be worth swapping in.",
    )

    class Config:
        extra = "allow"


class AlgorithmTrainingInfo(pydantic.BaseModel):
    """
    What actually happened when this version was trained. Written by the service, read-only.

    Every retrain produces a new algorithm version, so this is the record of where a
    particular set of weights came from.
    """

    trained_at: datetime.datetime | None = None
    dataset_url: str | None = pydantic.Field(default=None, description="The exact training set this was fitted on.")
    dataset_rows: int | None = None
    dataset_classes: int | None = None
    metrics: dict = pydantic.Field(default_factory=dict, description="Scores on the held-out split.")
    previous_metrics: dict = pydantic.Field(
        default_factory=dict, description="What the version it was compared against scored on the same rows."
    )
    parent_algorithm_key: str | None = pydantic.Field(
        default=None, description="The version this one was trained to beat."
    )
    job_id: int | None = None
    warnings: list[str] = pydantic.Field(default_factory=list)

    class Config:
        extra = "allow"


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
    trainable: bool = pydantic.Field(
        default=False,
        description=(
            "Whether this algorithm can be retrained from labelled data. A service usually hosts "
            "several algorithms and only some of them, typically a classifier head over a frozen "
            "backbone, are cheap enough to retrain."
        ),
    )
    training_config: AlgorithmTrainingConfig | None = pydantic.Field(
        default=None,
        description="The service's default retraining settings. Antenna seeds its own copy from this.",
    )
    training_info: AlgorithmTrainingInfo | None = pydantic.Field(
        default=None,
        description="Where this version's weights came from. Only set on a version that was retrained.",
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
    features: list[float] | None = pydantic.Field(
        default=None,
        description=(
            "The embedding the model's backbone produced for this crop, taken before the "
            "classification head. Optional, and only useful if every value comes from the "
            "same backbone."
        ),
    )
    inference_time: float | None = None
    algorithm: AlgorithmReference
    terminal: bool = True
    timestamp: datetime.datetime


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


class DetectionRequest(pydantic.BaseModel):
    source_image: SourceImageRequest  # the 'original' image
    bbox: BoundingBox | None = None
    crop_image_url: str | None = None
    algorithm: AlgorithmReference


class DetectionResponse(pydantic.BaseModel):
    source_image_id: str
    bbox: BoundingBox | None = None
    inference_time: float | None = None
    algorithm: AlgorithmReference
    timestamp: datetime.datetime
    crop_image_url: str | None = None
    classifications: list[ClassificationResponse] = []


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
    detections: list[DetectionRequest] | None = None
    config: PipelineRequestConfigParameters | dict | None = None

    def summary(self) -> str:
        """
        Return a human-friendly summary string of the request key details.
        (number of images, pipeline name, number of detections, etc.)

        e.g. "pipeline request with 10 images and 25 detections to 'panama_moths_2023'"

        Returns:
            str: A summary string.
        """

        num_images = len(self.source_images)
        num_detections = len(self.detections) if self.detections else 0
        return (
            f"pipeline request with {num_images} image{'s' if num_images != 1 else ''} "
            f"and {num_detections} detection{'s' if num_detections != 1 else ''} "
            f"to pipeline '{self.pipeline}'"
        )


class PipelineResultsResponse(pydantic.BaseModel):
    # pipeline: PipelineChoice
    pipeline: str
    algorithms: dict[str, AlgorithmConfigResponse] = pydantic.Field(
        default_factory=dict,
        description=(
            "A dictionary of all algorithms used in the pipeline, including their class list and other "
            "metadata, keyed by the algorithm key. "
            "DEPRECATED: Algorithms should only be provided in the ProcessingServiceInfoResponse."
        ),
        depreciated=True,
    )
    total_time: float
    source_images: list[SourceImageResponse]
    detections: list[DetectionResponse]
    errors: list | str | None = None


class PipelineResultsError(pydantic.BaseModel):
    """Error result when pipeline processing fails for an image."""

    error: str
    image_id: str | None = None


class PipelineProcessingTask(pydantic.BaseModel):
    """
    A task representing a single image or detection to be processed in an async pipeline.
    """

    id: str
    image_id: str
    image_url: str
    reply_subject: str | None = None  # The NATS subject to send the result to
    # TODO: Do we need these?
    # detections: list[DetectionRequest] | None = None
    # config: PipelineRequestConfigParameters | dict | None = None


class ProcessingServiceClientInfo(pydantic.BaseModel):
    """Identity metadata sent by a processing service worker.

    A single ProcessingService record in the database may have multiple
    physical workers, pods, or machines running simultaneously. This model
    lets the server distinguish between them for logging, debugging, and
    eventually for per-worker health tracking.

    Fields are intentionally left open for now. Processing services can
    send any key-value pairs they find useful (e.g. hostname, pod_name,
    software version). The schema will be tightened once real-world usage
    patterns emerge.
    """

    class Config:
        extra = "allow"


class PipelineTaskResult(pydantic.BaseModel):
    """
    The result from processing a single PipelineProcessingTask.

    Note: this schema is called `AntennaTaskResult` in the ADC worker processing service.
    """

    reply_subject: str  # The reply_subject from the PipelineProcessingTask
    result: PipelineResultsResponse | PipelineResultsError


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


class PipelineConfigResponse(pydantic.BaseModel):
    """
    Details of a pipeline available in the processing service.

    Includes the algorithm (model) definitions used in the pipeline, and
    their category maps (class lists).

    This must be retrieved from the processing service API and saved in Antenna
    before images are submitted for processing.
    """

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
    pipelines: list[PipelineConfigResponse] = []
    algorithms: list[AlgorithmConfigResponse] = []


class ProcessingServiceStatusResponse(pydantic.BaseModel):
    """
    Status response returned by the Antenna API about the Processing Service.
    """

    timestamp: datetime.datetime
    request_successful: bool
    pipeline_configs: list[PipelineConfigResponse] = []
    error: str | None = None
    server_live: bool | None = None
    pipelines_online: list[str] = []
    endpoint_url: str | None = None
    latency: float


class PipelineRegistrationResponse(pydantic.BaseModel):
    timestamp: datetime.datetime
    success: bool
    error: str | None = None
    pipelines: list[PipelineConfigResponse] = []
    pipelines_created: list[str] = []
    algorithms_created: list[str] = []


class AsyncPipelineRegistrationRequest(pydantic.BaseModel):
    """
    Request to register pipelines from an async processing service
    """

    processing_service_name: str
    pipelines: list[PipelineConfigResponse] = []
