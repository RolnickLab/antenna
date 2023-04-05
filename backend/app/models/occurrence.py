from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi_users_db_sqlalchemy import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime, String
from sqlalchemy.ext.hybrid import hybrid_property

from app.db import Base

if TYPE_CHECKING:
    from app.models.user import User  # noqa: F401
    from app.models.deployment import Deployment  # noqa: F401


class Occurrence(Base):
    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # The best prediction of the occurrence
    # taxon_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("taxa.id"))
    # taxon: Mapped["Taxon"] = relationship(back_populates="occurrences")

    # event_id: Mapped[UUID] = mapped_column(GUID, ForeignKey("events.id"))
    # event: Mapped["Event"] = relationship(back_populates="occurrences")

    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"))
    deployment: Mapped["Deployment"] = relationship(back_populates="occurrences")

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @hybrid_property
    def duration(self) -> timedelta:
        """Return the number of seconds the occurrence appeared."""
        return self.last_seen - self.first_seen
