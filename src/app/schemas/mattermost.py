from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator


class MattermostMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mm_post_id: str
    channel_id: str
    channel_name: str | None = None
    user_id: str
    user_display_name: str | None = None
    posted_at: datetime
    message: str
    post_type: str | None = None
    created_at: datetime
    updated_at: datetime


class MattermostMessagePage(BaseModel):
    items: list[MattermostMessageRead]
    total: int
    limit: int
    offset: int


# Hours of activity each channel shows, oldest first, the current hour last.
ACTIVITY_HOURS = 24


class ChannelRead(BaseModel):
    """A channel as the Comms page shows it: what the latest sweep found, and what Holly holds."""

    mm_channel_id: str
    name: str
    display_name: str | None
    team_name: str | None
    channel_type: str
    status: Literal["open", "closed"]
    archived: bool
    accessible: bool
    following: bool
    is_new: bool
    pulled: bool
    first_seen_at: datetime
    last_seen_at: datetime
    closed_at: datetime | None
    message_count: int
    last_message_at: datetime | None
    activity: list[int]
    # Messages Holly holds posted after the `since` the page asked about (the user's last
    # visit), or None when it asked about none.
    new_since: int | None = None


class SweepRead(BaseModel):
    # False when MATTERMOST_URL or MATTERMOST_BOT_TOKEN is unset: Holly then pulls nothing.
    configured: bool
    last_at: datetime | None
    ok: bool | None
    problem: str | None
    bot: str | None
    interval_seconds: int


class ChannelsResponse(BaseModel):
    channels: list[ChannelRead]
    sweep: SweepRead


class ChannelUpdate(BaseModel):
    following: StrictBool | None = None
    # Only the JSON value true: Literal[True] alone also takes 1, which equals True in Python.
    reviewed: Literal[True] | None = None

    @field_validator("reviewed", mode="before")
    @classmethod
    def _only_true(cls, value: object) -> object:
        if value is not None and value is not True:
            msg = "reviewed can only be true"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if self.following is None and self.reviewed is None:
            msg = "name following or reviewed"
            raise ValueError(msg)
        return self


class ReviewedResponse(BaseModel):
    reviewed: int


class SweepResponse(BaseModel):
    ok: bool | None
    problem: str | None
    found: int
    new: int
    closed: int
    reopened: int
    lost: int
    channels_polled: int
    channels_failed: int
    inserted: int
