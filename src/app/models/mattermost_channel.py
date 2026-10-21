import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, false, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MattermostChannel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A Mattermost channel the bot can read, as Holly's channel sweep last found it (ADR-015).

    The sweep lists the bot's public and private channels in every team it belongs to, never a
    direct or group message. A channel whose name holds the word CLOSED, in any case, or that is
    archived, is closed: Holly keeps what it pulled and pulls nothing more, until the word goes.
    A channel found for the first time is followed at once and is new until someone reviews it.
    """

    __tablename__ = "mattermost_channel"

    mm_channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Mattermost's type: "O" for a public channel, "P" for a private one.
    channel_type: Mapped[str] = mapped_column(String(8), nullable=False)
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    closed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # False once a complete sweep no longer finds it: the bot has left or lost the channel.
    accessible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    following: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    following_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    following_changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("mm_channel_id", name="uq_mattermost_channel_mm_channel_id"),
    )
