"""The Handover tab's reads and writes: the objects with live events, and one object's story
told from what Holly already holds, with where every item came from."""

import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.common import StorableText
from app.schemas.maneuver import ManeuverFacts


class HandoverObject(BaseModel):
    """An object named by a notice in the window."""

    sat_no: int
    name: str | None
    kinds: list[str]
    latest_at: datetime | None
    events: int
    maneuvers: int


class HandoverObjectList(BaseModel):
    window_hours: int
    window_start: datetime
    generated_at: datetime
    objects: list[HandoverObject]
    truncated: bool


class StoryNotice(BaseModel):
    """One publication of a notice about the object. `udl_id` is its UDL record."""

    id: UUID
    event_key: str
    notice: str | None
    event_class: str | None
    kind: str | None
    status: str | None
    udl_created_at: datetime | None
    source: str | None
    udl_id: str | None


class StoryManeuver(BaseModel):
    id: UUID
    source: str | None
    event_start_time: datetime | None
    maneuver_status: str | None
    udl_id: str | None
    facts: ManeuverFacts


class StoryPost(BaseModel):
    post_id: str
    posted_at: datetime
    author: str | None
    message: str


class StoryThread(BaseModel):
    """A chat thread a mission lead confirmed is about one of the object's notices."""

    thread_id: str
    event_keys: list[str]
    channel_name: str | None
    confirmed_at: datetime
    posts: list[StoryPost]
    truncated: bool


class ThreadSuggestion(BaseModel):
    """A thread that mentions the object or one of its notices, not yet decided on."""

    thread_id: str
    event_key: str
    channel_name: str | None
    reason: str
    first_post: StoryPost
    matching_posts: int


class StoryTimer(BaseModel):
    id: UUID
    label: str
    target_time: datetime
    event_key: str | None


class StoryNote(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID | None
    author: str | None = None
    text: str
    created_at: datetime


class HandoverStory(BaseModel):
    sat_no: int
    name: str | None
    window_hours: int
    window_start: datetime
    generated_at: datetime
    notices: list[StoryNotice]
    maneuvers: list[StoryManeuver]
    threads: list[StoryThread]
    suggestions: list[ThreadSuggestion]
    timers: list[StoryTimer]
    notes: list[StoryNote]
    truncated: bool


class ThreadLinkDecision(BaseModel):
    """Confirm or reject a suggested link, or clear an earlier decision."""

    model_config = ConfigDict(extra="forbid")

    thread_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    # Stripped before its length is checked, so a key of spaces alone is refused. A control
    # character, NUL among them, is refused by the pattern, and Pydantic refuses a lone
    # surrogate before any validator, so the key is always text Holly can store.
    event_key: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00-\x1f\x7f]+$"
        ),
    ]
    decision: Literal["confirmed", "rejected", "clear"]


class HandoverNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: StorableText = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def _no_format_characters(cls, value: str) -> str:
        """Drops Unicode format characters (bidirectional overrides, zero-width spaces), so a
        note cannot show in another order than it is stored."""
        return "".join(ch for ch in value if unicodedata.category(ch) != "Cf")
