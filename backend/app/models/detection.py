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
    from app.models.deployment import Deployment  # noqa: F401
    from app.models.taxon import Taxon # noqa: F401
    from app.models.classification import Classification # noqa: F401
    from app.models.occurrence import Occurrence # noqa: F401


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    path: Mapped[str]

    # occurrence_id: Mapped[int] = mapped_column(ForeignKey("occurrences.id"))
    # occurrence: Mapped["Occurrence"] = relationship(back_populates="detections") 

    # classifications: Mapped[List["Classification"]] = relationship(back_populates="detection")

    # deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"))
    # deployment: Mapped["Deployment"] = relationship(back_populates="detections")

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
