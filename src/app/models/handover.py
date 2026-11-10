import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

CONFIRMED = "confirmed"
REJECTED = "rejected"


class HandoverThreadLink(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A mission lead's decision that a Mattermost thread is, or is not, about a logical notice.

    Holly suggests links from NOTSO numbers and catalogue numbers in the chat; it never assumes
    one. Only a confirmed link puts a thread into an object's story; a rejected one stops the
    suggestion coming back. `thread_id` is the thread's root post id, `event_key` the notice's
    group key (services/notification_query.py).
    """

    __tablename__ = "handover_thread_link"

    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("thread_id", "event_key", name="uq_handover_thread_link"),
        CheckConstraint(
            "decision IN ('confirmed', 'rejected')", name="ck_handover_thread_link_decision"
        ),
        Index("ix_handover_thread_link_event_key", "event_key"),
    )


class HandoverNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An analyst's free-text note on one object, by catalogue number."""

    __tablename__ = "handover_note"

    sat_no: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_handover_note_sat_no", "sat_no"),)
