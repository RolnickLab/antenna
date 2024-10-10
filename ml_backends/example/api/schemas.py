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


class SourceImage(pydantic.BaseModel):
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


class Classification(pydantic.BaseModel):
    classification: str
    labels: list[str] = []
    scores: list[float] = []
    inference_time: float | None = None
    algorithm: str
    terminal: bool = True
    timestamp: datetime.datetime


class Detection(pydantic.BaseModel):
    source_image_id: str
    bbox: BoundingBox
    inference_time: float | None = None
    algorithm: str
    timestamp: datetime.datetime
    crop_image_url: str | None = None
    classifications: list[Classification] = []


class SourceImageRequest(pydantic.BaseModel):
    # @TODO bring over new SourceImage & b64 validation from the lepsAI repo
    id: str
    url: str
    # b64: str | None = None

    class Config:
        extra = "ignore"


class SourceImageResponse(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="ignore")

    id: str
    url: str


PipelineChoice = typing.Literal["dummy"]


class PipelineRequest(pydantic.BaseModel):
    pipeline: PipelineChoice
    source_images: list[SourceImageRequest]

    # Example for API docs:
    class Config:
        json_schema_extra = {
            "example": {
                "pipeline": "random",
                "source_images": [
                    {
                        "id": "123",
                        "url": "https://example.com/image.jpg",
                    }
                ],
            }
        }


class PipelineResponse(pydantic.BaseModel):
    pipeline: PipelineChoice
    total_time: float
    source_images: list[SourceImageResponse]
    detections: list[Detection]


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
    description: str | None = None  # @TODO: python type annotations
    stages: list[PipelineStage] = []
