from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.sqltypes import DateTime
from sqlalchemy.ext.hybrid import hybrid_property

from app.db import Base

if TYPE_CHECKING:
    from app.models.event import Event  # noqa: F401
    from app.models.source_image import SourceImage  # noqa: F401
    from app.models.detection import Detection  # noqa: F401
    from app.models.occurrence import Occurrence


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    source_data: Mapped[str]
    location: Mapped[str]
    description: Mapped[str]

    events: Mapped[List["Event"]] = relationship(back_populates="deployment")
    source_images: Mapped[List["SourceImage"]] = relationship(back_populates="deployment")
    detections: Mapped[List["Detection"]] = relationship(back_populates="deployment")
    occurrences: Mapped[List["Occurrence"]] = relationship(back_populates="deployment")

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

