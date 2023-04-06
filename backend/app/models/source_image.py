from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional
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
    from app.models.event import Event # noqa: F401


class SourceImage(Base):
    __tablename__ = "source_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    path: Mapped[str]
    width: Mapped[int]
    height: Mapped[int]
    hash: Mapped[str]

    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"))
    deployment: Mapped["Deployment"] = relationship(back_populates="source_images")

    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    event: Mapped[Optional["Event"]] = relationship(back_populates="source_images")

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
