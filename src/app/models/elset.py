from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UDLSourceMixin, UUIDPrimaryKeyMixin


class Elset(Base, UUIDPrimaryKeyMixin, UDLSourceMixin, TimestampMixin):
    __tablename__ = "elset"

    sat_no: Mapped[int] = mapped_column(Integer, nullable=False)
    epoch: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    mean_motion: Mapped[float | None] = mapped_column(Float, nullable=True)
    eccentricity: Mapped[float | None] = mapped_column(Float, nullable=True)
    inclination: Mapped[float | None] = mapped_column(Float, nullable=True)
    raan: Mapped[float | None] = mapped_column(Float, nullable=True)
    arg_of_perigee: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_anomaly: Mapped[float | None] = mapped_column(Float, nullable=True)

    rev_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bstar: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_motion_dot: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_motion_ddot: Mapped[float | None] = mapped_column(Float, nullable=True)

    semi_major_axis: Mapped[float | None] = mapped_column(Float, nullable=True)
    period: Mapped[float | None] = mapped_column(Float, nullable=True)
    apogee: Mapped[float | None] = mapped_column(Float, nullable=True)
    perigee: Mapped[float | None] = mapped_column(Float, nullable=True)

    line1: Mapped[str | None] = mapped_column(String(70), nullable=True)
    line2: Mapped[str | None] = mapped_column(String(70), nullable=True)

    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("udl_id", name="uq_elset_udl_id"),
        Index("ix_elset_sat_no", "sat_no"),
        Index("ix_elset_epoch", "epoch"),
        Index("ix_elset_sat_no_epoch", "sat_no", "epoch"),
    )
