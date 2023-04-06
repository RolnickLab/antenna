import datetime
import pathlib
from typing import Optional

from pydantic import BaseModel


class OccurrenceCreate(BaseModel):
    label: str
    score: float
    sequence_id: int
    start_time: datetime.datetime
    end_time: datetime.datetime
    duration: datetime.timedelta
    cropped_image_path: pathlib.Path
    detections: Optional[list[object]]
    deployment: Optional[object]
    captures: Optional[list[object]]


class OccurrenceUpdate(OccurrenceCreate):
    pass


class Occurrence(OccurrenceCreate):
    id: int

    class Config:
        orm_mode = True


test_data = [
    Occurrence(
        id="1",
        label="Acmon blue",
        score=0.8702,
        sequence_id=521,
        start_time=datetime.datetime.now(),
        end_time=datetime.datetime.now(),
        duration=datetime.datetime.now() - datetime.datetime.today(),
        cropped_image_path="/crops/acmon_blue.jpg",
    )
]
