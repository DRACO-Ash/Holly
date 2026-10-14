from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Recurrence = Literal["none", "daily", "weekly", "monthly"]

# The years a timer may target. Far outside them a recurrence could overflow the calendar or
# take a long walk to its next occurrence.
EARLIEST_TARGET = datetime(2000, 1, 1, tzinfo=UTC)
LATEST_TARGET = datetime(2100, 1, 1, tzinfo=UTC)


class EventTimerCreate(BaseModel):
    # At least one character that is not whitespace: the label is stored stripped.
    label: str = Field(min_length=1, max_length=200, pattern=r"\S")
    target_time: datetime
    event_key: str | None = Field(default=None, max_length=200)
    pre_alert_minutes: int = Field(default=5, ge=0, le=720)
    recurrence: Recurrence = "none"
    shift_date: date | None = None

    @field_validator("target_time")
    @classmethod
    def _within_range(cls, value: datetime) -> datetime:
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if not EARLIEST_TARGET <= aware < LATEST_TARGET:
            msg = "target_time must fall between the years 2000 and 2099"
            raise ValueError(msg)
        return value


class EventTimerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_key: str | None = None
    label: str
    target_time: datetime
    pre_alert_minutes: int
    recurrence: str
    pre_alert_fired_at: datetime | None = None
    dismissed_at: datetime | None = None
    dismissed_by: UUID | None = None
    created_by: UUID | None = None
    shift_date: date | None = None
    created_at: datetime
    updated_at: datetime


class EventTimerList(BaseModel):
    items: list[EventTimerRead]
