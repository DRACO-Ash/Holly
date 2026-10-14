import uuid
from datetime import date as date_t
from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EventTimer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Operator-set countdown to an upcoming event.

    The frontend fires an audible and visual pre-alert at
    `target_time - pre_alert_minutes`, then recurring alerts every
    cycle from `target_time` until `dismissed_at` is set.

    Lifecycle:
    ● upcoming: now < target_time - pre_alert_minutes
    ● pre-alert: target_time - pre_alert_minutes <= now < target_time;
      one-shot warning, dampened by pre_alert_fired_at
    ● firing: now >= target_time and dismissed_at is null
    ● dismissed: dismissed_at is set; recurring alerts stop
    """

    __tablename__ = "event_timer"

    event_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    target_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pre_alert_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    # "none" | "daily" | "weekly" | "monthly". Recurring timers roll
    # forward to the next occurrence when dismissed instead of going
    # permanently dismissed.
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    # The first occurrence a recurring timer counts from, so a monthly timer set for the 31st
    # comes back to the 31st after a shorter month. Null on timers created before migration
    # 0016 until their next roll forward.
    recurrence_anchor: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    pre_alert_fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    shift_date: Mapped[date_t | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        Index("ix_event_timer_target_time", "target_time"),
        Index("ix_event_timer_dismissed_at", "dismissed_at"),
        Index("ix_event_timer_event_key", "event_key"),
    )
