"""The declarative base and the column groups several tables share.

The migrations (migrations/versions) define the schema; these classes describe the same
columns to the ORM. A mixin changes nothing in the database.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UDLSourceMixin:
    """The UDL identity and provenance every UDL-sourced table keeps (ADR-007)."""

    udl_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_marking: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)


class UDLEnvelopeMixin(UDLSourceMixin):
    """The fuller UDL envelope on notifications and maneuvers."""

    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    orig_network: Mapped[str | None] = mapped_column(String(50), nullable=True)
    udl_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
