## pydantic schemas for all models

from typing import List, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.types import PositiveInt



class TaxonBase(BaseModel):
    name: str
    parent_id: Optional[PositiveInt] = None

class TaxonCreate(TaxonBase):
    pass

class TaxonUpdate(TaxonBase):
    pass

class Taxon(TaxonBase):
    id: PositiveInt
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True


class DeploymentBase(BaseModel):
    name: str

class DeploymentCreate(DeploymentBase):
    pass

class DeploymentUpdate(DeploymentBase):
    pass

class Deployment(DeploymentBase):
    id: PositiveInt
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True


class EventBase(BaseModel):
    name: str
    deployment_id: PositiveInt

class EventCreate(EventBase):
    pass

class EventUpdate(EventBase):
    pass

class Event(EventBase):
    id: PositiveInt
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True


class SourceImageBase(BaseModel):
    timestamp: datetime
    path: str
    width: PositiveInt
    height: PositiveInt
    hash: str
    deployment_id: PositiveInt
    event_id: Optional[PositiveInt] = None

class SourceImageCreate(SourceImageBase):
    pass

class SourceImageUpdate(SourceImageBase):
    pass

class SourceImage(SourceImageBase):
    id: PositiveInt
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True


class OccurrenceBase(BaseModel):
    taxon_id: PositiveInt
    event_id: PositiveInt
    source_image_id: PositiveInt

class OccurrenceCreate(OccurrenceBase):
    pass

class OccurrenceUpdate(OccurrenceBase):
    pass

class Occurrence(OccurrenceBase):
    id: PositiveInt
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True


class DetectionBase(BaseModel):
    source_image_id: PositiveInt
    deployment_id: PositiveInt
    event_id: Optional[PositiveInt] = None

class DetectionCreate(DetectionBase):
    pass

class DetectionUpdate(DetectionBase):
    pass

class Detection(DetectionBase):
    id: PositiveInt
    created: datetime
    updated: datetime

    class Config:
        orm_mode = True






