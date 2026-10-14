from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
