from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.types import JSON

from app.db import Base

if TYPE_CHECKING:
    from app.models.deployment import Deployment  # noqa: F401
    from app.models.taxon import Taxon  # noqa: F401


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    score: Mapped[float]
    model: Mapped[str]
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON)

    taxon_id: Mapped[int] = mapped_column(ForeignKey("taxa.id"))
    taxon: Mapped["Taxon"] = relationship(back_populates="classifications")

    detection_id: Mapped[int] = mapped_column(ForeignKey("detections.id"))
    detection: Mapped["Deployment"] = relationship(back_populates="classifications")

    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"))
    deployment: Mapped["Deployment"] = relationship(back_populates="classifications")

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
