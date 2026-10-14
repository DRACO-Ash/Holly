from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ShiftNoteCreate(BaseModel):
    raw_text: str = Field(min_length=1, max_length=10_000)
    shift_date: date | None = None


class ShiftNoteUpdate(BaseModel):
    polished_text: str | None = Field(default=None, max_length=10_000)


class ShiftNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID | None = None
    shift_date: date
    raw_text: str
    polished_text: str | None = None
    polish_error: str | None = None
    model: str | None = None
    created_at: datetime
    updated_at: datetime


class ShiftNoteList(BaseModel):
    items: list[ShiftNoteRead]
    shift_date: date


class ShiftSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shift_date: date
    generated_by: UUID | None = None
    narrative: str
    source_note_ids: list[str]
    model: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ShiftDateSummary(BaseModel):
    """A shift date that has at least one note logged against it."""

    shift_date: date
    note_count: int
    has_summary: bool


class ShiftDateList(BaseModel):
    items: list[ShiftDateSummary]
