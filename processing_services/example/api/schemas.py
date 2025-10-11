# Can these be imported from the OpenAPI spec yaml?
import datetime
import logging
import pathlib
import typing

import PIL.Image
import pydantic

from .utils import get_image

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class BoundingBox(pydantic.BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @classmethod
    def from_coords(cls, coords: list[float]):
        return cls(x1=coords[0], y1=coords[1], x2=coords[2], y2=coords[3])

    def to_string(self):
        return f"{self.x1},{self.y1},{self.x2},{self.y2}"

    def to_path(self):
        return "-".join([str(int(x)) for x in [self.x1, self.y1, self.x2, self.y2]])

    def to_tuple(self):
        return (self.x1, self.y1, self.x2, self.y2)


class BaseImage(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    id: str
    url: str | None = None
    b64: str | None = None
    filepath: str | pathlib.Path | None = None
    _pil: PIL.Image.Image | None = None
    width: int | None = None
    height: int | None = None
    timestamp: datetime.datetime | None = None

    # Validate that there is at least one of the following fields
    @pydantic.model_validator(mode="after")
    def validate_source(self):
        if not any([self.url, self.b64, self.filepath, self._pil]):
            raise ValueError("At least one of the following fields must be provided: url, b64, filepath, pil")
        return self

    def open(self, raise_exception=False) -> PIL.Image.Image | None:
        if not self._pil:
            logger.warn(f"Opening image {self.id} for the first time")
            self._pil = get_image(
                url=self.url,
                b64=self.b64,
                filepath=self.filepath,
                raise_exception=raise_exception,
            )
        else:
            logger.info(f"Using already loaded image {self.id}")
        if self._pil:
            self.width, self.height = self._pil.size
        return self._pil


class SourceImage(BaseImage):
    pass


class AlgorithmReference(pydantic.BaseModel):
    name: str
    key: str


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
    scores: list[float] = pydantic.Field(
        default_factory=list,
        description="The calibrated probabilities for each class label, most commonly the softmax output.",
    )
    logits: list[float] = pydantic.Field(
        default_factory=list,
        description="The raw logits output by the model, before any calibration or normalization.",
    )
    inference_time: float | None = None
    algorithm: AlgorithmReference
    terminal: bool = True
    timestamp: datetime.datetime


class SourceImageRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="ignore")

    id: str
    url: str
    # b64: str | None = None
    # @TODO bring over new SourceImage & b64 validation from the lepsAI repo


class SourceImageResponse(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="ignore")

    id: str
    url: str


class DetectionRequest(pydantic.BaseModel):
    source_image: SourceImageRequest  # the 'original' image
    bbox: BoundingBox
    crop_image_url: str | None = None
    algorithm: AlgorithmReference


class DetectionResponse(pydantic.BaseModel):
    # these fields are populated with values from a Detection, excluding source_image details
    source_image_id: str
    bbox: BoundingBox
    inference_time: float | None = None
    algorithm: AlgorithmReference
    timestamp: datetime.datetime
    crop_image_url: str | None = None
    classifications: list[ClassificationResponse] = []


class Detection(BaseImage):
    """
    An internal representation of a detection with reference to a source image instance.
    """

    source_image: SourceImage  # the 'original' uncropped image
    bbox: BoundingBox
    inference_time: float | None = None
    algorithm: AlgorithmReference
    classifications: list[ClassificationResponse] = []


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
        description="A URI to the weights or model details, could be a public web URL or object store path.",
    )
    category_map: AlgorithmCategoryMapResponse | None = None

    class Config:
        extra = "ignore"


PipelineChoice = typing.Literal[
    "zero-shot-hf-classifier-pipeline",
    "zero-shot-object-detector-pipeline",
    "zero-shot-object-detector-with-constant-classifier-pipeline",
    "zero-shot-object-detector-with-random-species-classifier-pipeline",
    "zero-shot-object-detector-with-global-moth-classifier-pipeline",
]


class PipelineRequestConfigParameters(pydantic.BaseModel):
    """Parameters used to configure a pipeline request.

    Accepts any serializable key-value pair.
    Example: {"force_reprocess": True, "auth_token": "abc123"}

    Supported parameters are defined by the pipeline in the processing service
    and should be published in the Pipeline's info response.
    """

    force_reprocess: bool = pydantic.Field(
        default=False,
        description="Force reprocessing of the image, even if it has already been processed.",
    )
    auth_token: str | None = pydantic.Field(
        default=None,
        description="An optional authentication token to use for the pipeline.",
    )
    candidate_labels: list[str] | None = pydantic.Field(
        default=None,
        description="A list of candidate labels to use for the zero-shot object detector.",
    )


class PipelineRequest(pydantic.BaseModel):
    pipeline: PipelineChoice
    source_images: list[SourceImageRequest]
    detections: list[DetectionRequest] | None = None
    config: PipelineRequestConfigParameters | dict | None = None

    # Example for API docs:
    class Config:
        json_schema_extra = {
            "example": {
                "pipeline": "random",
                "source_images": [
                    {
                        "id": "123",
                        "url": "https://archive.org/download/mma_various_moths_and_butterflies_54143/54143.jpg",
                    }
                ],
                "config": {"force_reprocess": True, "auth_token": "abc123"},
            }
        }


class PipelineResultsResponse(pydantic.BaseModel):
    pipeline: PipelineChoice
    total_time: float
    algorithms: dict[str, AlgorithmConfigResponse] = pydantic.Field(
        default_factory=dict,
        description=(
            "A dictionary of all algorithms used in the pipeline, including their class list and other "
            "metadata, keyed by the algorithm key. "
            "DEPRECATED: Algorithms should only be provided in the ProcessingServiceInfoResponse."
        ),
        depreciated=True,
    )
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


class PipelineConfigResponse(pydantic.BaseModel):
    """Details about a pipeline, its algorithms and category maps."""

    name: str
    slug: str
    version: int
    description: str | None = None
    algorithms: list[AlgorithmConfigResponse] = []
    stages: list[PipelineStage] = []


class ProcessingServiceInfoResponse(pydantic.BaseModel):
    """Information about the processing service."""

    name: str = pydantic.Field(example="Mila Research Lab - Moth AI Services")
    description: str | None = pydantic.Field(
        default=None,
        examples=["Algorithms developed by the Mila Research Lab for analysis of moth images."],
    )
    pipelines: list[PipelineConfigResponse] = pydantic.Field(
        default=list,
        examples=[
            [
                PipelineConfigResponse(name="Random Pipeline", slug="random", version=1, algorithms=[]),
            ]
        ],
    )
    # algorithms: list[AlgorithmConfigResponse] = pydantic.Field(
    #    default=list,
    #    examples=[RANDOM_BINARY_CLASSIFIER],
    # )
