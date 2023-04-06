from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, List
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime
from sqlalchemy.ext.hybrid import hybrid_property

from app.db import Base

if TYPE_CHECKING:
    from app.models.user import User  # noqa: F401
    from app.models.deployment import Deployment  # noqa: F401
    from app.models.taxon import Taxon  # noqa: F401
    from app.models.source_image import SourceImage  # noqa: F401 


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    # Calculated from the detections
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    source_images: Mapped[List["SourceImage"]] = relationship(back_populates="event")

    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"))
    deployment: Mapped["Deployment"] = relationship(back_populates="events")

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @hybrid_property
    def duration(self) -> timedelta:
        """Return the number of seconds the occurrence appeared."""
        return self.end - self.start

    @hybrid_property
    def num_images(self) -> int:
        """Return the number of images in the event."""
        return len(self.source_images)

