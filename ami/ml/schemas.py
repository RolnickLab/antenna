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


class DetectionResponse(pydantic.BaseModel):
    source_image_id: str
    bbox: BoundingBox
    inference_time: float | None = None
    algorithm: str | None = None
    timestamp: datetime.datetime
    crop_image_url: str | None = None


class ClassificationResponse(pydantic.BaseModel):
    source_image_id: str
    bbox: BoundingBox | None = None
    classification: str
    labels: list[str] = []
    scores: list[float] = []
    inference_time: float | None = None
    algorithm: str | None = None
    timestamp: datetime.datetime


class SourceImageRequest(pydantic.BaseModel):
    # @TODO bring over new SourceImage & b64 validation from the lepsAI repo
    id: str
    url: str
    # b64: str | None = None


class SourceImageResponse(pydantic.BaseModel):
    id: str
    url: str


PipelineChoice = typing.Literal[
    "panama_moths_2023",
    "quebec_vermont_moths_2023",
    "uk_denmark_moths_2023",
]


class PipelineRequest(pydantic.BaseModel):
    pipeline: PipelineChoice
    source_images: list[SourceImageRequest]


class PipelineResponse(pydantic.BaseModel):
    pipeline: PipelineChoice
    total_time: float
    source_images: list[SourceImageResponse]
    detections: list[DetectionResponse]
    classifications: list[ClassificationResponse]
