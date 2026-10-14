from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UDLEnvelopeMixin, UUIDPrimaryKeyMixin


class Maneuver(Base, UUIDPrimaryKeyMixin, UDLEnvelopeMixin, TimestampMixin):
    """UDL maneuver record uploaded by fusion providers.

    Typed columns mirror the commonly-queried fields of the UDL
    maneuver schema; everything else is preserved verbatim in `raw`
    so anything not promoted is still queryable via JSONB ops.
    """

    __tablename__ = "maneuver"

    origin: Mapped[str | None] = mapped_column(String(100), nullable=True)

    sat_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    event_stop_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    mnvr_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    delta_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    thrust_magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    thrust_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    propulsion_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    maneuver_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    responsible_nation: Mapped[str | None] = mapped_column(String(50), nullable=True)

    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("udl_id", name="uq_maneuver_udl_id"),
        Index("ix_maneuver_sat_no", "sat_no"),
        Index("ix_maneuver_event_start_time", "event_start_time"),
        Index("ix_maneuver_mnvr_type", "mnvr_type"),
        Index("ix_maneuver_udl_created_at", "udl_created_at"),
    )
