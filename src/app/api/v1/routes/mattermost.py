from datetime import datetime
from operator import eq, ge
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.v1.common import Offset, fetch_page, present_filters
from app.dependencies import CurrentUser, DbSession
from app.models.mattermost_message import MattermostMessage
from app.schemas.common import StorableText
from app.schemas.mattermost import MattermostMessagePage, MattermostMessageRead

router = APIRouter(prefix="/mattermost", tags=["mattermost"])


@router.get("/messages")
async def list_messages(
    db: DbSession,
    _current_user: CurrentUser,
    channel_id: StorableText | None = None,
    user_id: StorableText | None = None,
    posted_at_gte: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Offset = 0,
) -> MattermostMessagePage:
    base = select(MattermostMessage).where(
        *present_filters(
            [
                (channel_id, MattermostMessage.channel_id, eq),
                (user_id, MattermostMessage.user_id, eq),
                (posted_at_gte, MattermostMessage.posted_at, ge),
            ]
        )
    )
    order = [MattermostMessage.posted_at.desc()]
    items, total = await fetch_page(db, base, order, limit, offset)
    return MattermostMessagePage(
        items=[MattermostMessageRead.model_validate(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )
