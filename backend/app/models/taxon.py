from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.sql.sqltypes import DateTime


from app.db import Base


class Taxon(Base):
    __tablename__ = "taxa"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    rank: Mapped[str]
    gbif_id: Mapped[int]
    parent_id: Mapped[int] = mapped_column(ForeignKey("taxa.id"))
    parent: Mapped["Taxon"] = relationship(back_populates="children")

    species: Mapped[str]
    genus: Mapped[str | None]
    family: Mapped[str | None]
    superfamily: Mapped[str | None]
    order: Mapped[str | None]

    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
