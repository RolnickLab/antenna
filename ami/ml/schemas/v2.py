import typing

from pydantic import BaseModel


class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class StageVersion(BaseModel):
    algorithm: str
    apiVersion: str
    modelVersion: str

    def __str__(self):
        return f"{self.algorithm} {self.apiVersion} {self.modelVersion}"


class Timing(BaseModel):
    http: float
    inference: float
    total: float


class ClassificationCallbackResponse(BaseModel):
    algorithm: str
    labelIds: typing.Sequence[str]
    labelNames: typing.Sequence[str]
    displayScores: typing.Sequence[int]
    scores: typing.Sequence[float]


class CnnFeatures(BaseModel):
    version: StageVersion
    url: str


class DetectionCallbackResponse(BaseModel):
    id: str
    cropUrl: str
    version: StageVersion
    boundingBox: BoundingBox
    classifications: typing.Sequence[ClassificationCallbackResponse]
    cnnFeatures: CnnFeatures | None = None


class StageResponseInformation(BaseModel):
    taskId: str
    version: StageVersion
    timing: Timing
    timestamp: int


class SourceImageResponse(BaseModel):
    sourceImageId: str
    sourceImageUrl: str
    eventId: str
    stages: typing.Sequence[StageResponseInformation]
    detections: typing.Sequence[DetectionCallbackResponse]


class PipelineCallbackResponse(BaseModel):
    jobId: str
    pipelineRequestId: str
    data: typing.Sequence[SourceImageResponse]


class SourceImageRequest(BaseModel):
    id: str
    url: str
    eventId: str


class StageConfig(BaseModel):
    stage: typing.Literal[
        "OBJECT_DETECTION",
        "IMAGE_CROP",
        "CLASSIFICATION",
        "CONDITIONAL_STAGE_SELECTOR",
        "CNN_FEATURE_CLASSIFIER",
    ]
    stageImplementation: str


class PipelineConfig(BaseModel):
    stages: typing.Sequence[StageConfig]


class PipelineCallbackConfig(BaseModel):
    callbackUrl: str
    callbackToken: str


class PipelineAsyncRequestData(BaseModel):
    projectId: str
    jobId: str
    sourceImages: typing.Sequence[SourceImageRequest]
    pipelineConfig: PipelineConfig
    callback: PipelineCallbackConfig


class PipelineAsyncRequestResponse(BaseModel):
    requestId: str
