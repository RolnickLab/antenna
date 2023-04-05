import datetime
from pydantic import BaseModel


class OccurrenceCreate(BaseModel):
    value: str
    first_seen: datetime.datetime
    last_seen: datetime.datetime
    duration: datetime.timedelta
    deployment_id: int


class OccurrenceUpdate(OccurrenceCreate):
    pass


class Occurrence(OccurrenceCreate):
    id: int

    class Config:
        orm_mode = True
