import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EventSummary(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Claude-generated 3-sentence narrative of a single logical event's evolution.

    Keyed on `event_key`, the same COALESCE(event_id, notso_identifier,
    udl_id) value the deduped notification view uses. One row per
    logical event; updated when a fresh UDL publication for that event
    arrives.
    """

    __tablename__ = "event_summary"

    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    source_notification_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    latest_notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification.id", ondelete="SET NULL"),
        nullable=True,
    )
    publication_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("event_key", name="uq_event_summary_event_key"),
        Index("ix_event_summary_latest_notification", "latest_notification_id"),
    )
