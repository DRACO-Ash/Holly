import uuid
from datetime import date as date_t

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ShiftNote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An operator comment from the ops floor.

    The operator types the raw text; Claude rewrites it for clarity
    and tone. Both versions are stored so the operator can always go
    back to what they actually said and so a failed polish doesn't
    lose the underlying observation.
    """

    __tablename__ = "shift_note"

    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    shift_date: Mapped[date_t] = mapped_column(Date, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    polished_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    polish_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_shift_note_shift_date", "shift_date"),
        Index("ix_shift_note_author_id", "author_id"),
    )
