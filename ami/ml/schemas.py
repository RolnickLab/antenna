import datetime
import typing

import pydantic


class BoundingBox(pydantic.BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @classmethod
    def from_coords(cls, coords: list[float]):
        return cls(x1=coords[0], y1=coords[1], x2=coords[2], y2=coords[3])


class ClassificationResponse(pydantic.BaseModel):
    classification: str
    labels: list[str] = []  # class names, possibly only the top N
    scores: list[float] = (
        []
    )  # class probabilities / confidence scores, calibrated by the model, same length and order as labels list
    inference_time: float | None = None
    algorithm: str | None = None
    timestamp: datetime.datetime
    logits: list[float] | None = None  # raw output from last layer of model, all classes in original order
    terminal: bool = True


class DetectionResponse(pydantic.BaseModel):
    source_image_id: str
    bbox: BoundingBox
    inference_time: float | None = None
    algorithm: str | None = None
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


KnownPipelineChoices = typing.Literal[
    "panama_moths_2023",
    "quebec_vermont_moths_2023",
    "uk_denmark_moths_2023",
]


class PipelineRequest(pydantic.BaseModel):
    pipeline: str
    source_images: list[SourceImageRequest]


class PipelineResponse(pydantic.BaseModel):
    # pipeline: PipelineChoice
    pipeline: str
    total_time: float
    source_images: list[SourceImageResponse]
    detections: list[DetectionResponse]
