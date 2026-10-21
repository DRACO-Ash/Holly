"""The Comms page's routes: the stored messages, the channels the bot can read, and the follow
list, which any signed-in user may change (ADR-015). Each change to a channel is audited.

A channel's activity is counted in whole UTC hours from the epoch, so the buckets do not depend
on the database session's time zone.
"""

import math
from collections.abc import Sequence
from datetime import UTC, datetime
from operator import eq, ge
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import AwareDatetime
from sqlalchemy import ColumnElement, String, any_, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.common import Offset, fetch_page, present_filters
from app.config import get_settings
from app.core.net import client_ip
from app.core.rate_limit import MATTERMOST_SWEEP_LIMIT
from app.dependencies import CurrentUser, DbSession
from app.models.mattermost_channel import MattermostChannel
from app.models.mattermost_message import MattermostMessage
from app.models.user import User
from app.schemas.common import StorableText
from app.schemas.mattermost import (
    ACTIVITY_HOURS,
    ChannelRead,
    ChannelsResponse,
    ChannelUpdate,
    MattermostMessagePage,
    MattermostMessageRead,
    ReviewedResponse,
    SweepRead,
    SweepResponse,
)
from app.services.audit import write_audit
from app.services.background_refresh import run_mattermost_now
from app.services.mattermost_channels import SWEEP_STATE, SweepResult, is_pulled
from app.services.mattermost_ingest import configured

router = APIRouter(prefix="/mattermost", tags=["mattermost"])

# A Mattermost channel id, as the client checks every id it puts in a path.
ChannelId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
MAX_CHANNEL_FILTER = 200
MAX_SEARCH_LENGTH = 200
_HOUR = 3600

AUDIT_CHANNEL_UPDATE = "mattermost.channel.update"
AUDIT_CHANNEL_REVIEW = "mattermost.channel.review"


def _any_of(ids: Sequence[str]) -> ColumnElement[bool]:
    """The message's channel is one of `ids`, sent as one array parameter rather than one
    parameter per id."""
    return MattermostMessage.channel_id == any_(literal(list(ids), ARRAY(String)))


def _contains(text: str) -> str:
    """A LIKE pattern matching `text` anywhere, its own wildcards taken literally."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get("/messages")
async def list_messages(
    db: DbSession,
    _current_user: CurrentUser,
    channel_id: Annotated[list[StorableText] | None, Query()] = None,
    followed: bool = False,
    user_id: StorableText | None = None,
    posted_at_gte: datetime | None = None,
    q: Annotated[StorableText | None, Query(max_length=MAX_SEARCH_LENGTH)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Offset = 0,
) -> MattermostMessagePage:
    """Messages newest first, from any of the channels named (repeat `channel_id`), with
    `followed` only from the followed open channels, and holding `q` when given, in any case."""
    if channel_id is not None and len(channel_id) > MAX_CHANNEL_FILTER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Name at most {MAX_CHANNEL_FILTER} channels.",
        )
    conditions = present_filters(
        [
            (user_id, MattermostMessage.user_id, eq),
            (posted_at_gte, MattermostMessage.posted_at, ge),
        ]
    )
    if channel_id:
        conditions.append(_any_of(channel_id))
    if followed:
        followed_open = select(MattermostChannel.mm_channel_id).where(
            MattermostChannel.following.is_(True), MattermostChannel.closed.is_(False)
        )
        conditions.append(MattermostMessage.channel_id.in_(followed_open))
    if q and q.strip():
        conditions.append(MattermostMessage.message.ilike(_contains(q.strip()), escape="\\"))
    base = select(MattermostMessage).where(*conditions)
    order = [MattermostMessage.posted_at.desc()]
    items, total = await fetch_page(db, base, order, limit, offset)
    return MattermostMessagePage(
        items=[MattermostMessageRead.model_validate(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _counts_since(db: AsyncSession, ids: list[str], since: datetime) -> dict[str, int]:
    """How many messages Holly holds from each channel posted after `since`."""
    result = await db.execute(
        select(MattermostMessage.channel_id, func.count())
        .where(_any_of(ids), MattermostMessage.posted_at > since)
        .group_by(MattermostMessage.channel_id)
    )
    return {channel: int(count) for channel, count in result.all()}


async def _channel_reads(
    db: AsyncSession, rows: Sequence[MattermostChannel], since: datetime | None = None
) -> list[ChannelRead]:
    """Each channel with what Holly holds of it: its message count, its newest message, its
    messages in each of the last 24 hours, and, when asked, how many arrived after `since`."""
    if not rows:
        return []
    ids = [row.mm_channel_id for row in rows]
    totals = {
        channel: (count, newest)
        for channel, count, newest in (
            await db.execute(
                select(
                    MattermostMessage.channel_id,
                    func.count(),
                    func.max(MattermostMessage.posted_at),
                )
                .where(_any_of(ids))
                .group_by(MattermostMessage.channel_id)
            )
        ).all()
    }
    first_hour = math.floor(datetime.now(UTC).timestamp() / _HOUR) - ACTIVITY_HOURS + 1
    hour = func.floor(func.extract("epoch", MattermostMessage.posted_at) / _HOUR).label("hour")
    activity: dict[str, list[int]] = {}
    for channel, bucket, count in (
        await db.execute(
            select(MattermostMessage.channel_id, hour, func.count())
            .where(
                _any_of(ids),
                MattermostMessage.posted_at >= datetime.fromtimestamp(first_hour * _HOUR, tz=UTC),
            )
            .group_by(MattermostMessage.channel_id, hour)
        )
    ).all():
        index = int(bucket) - first_hour
        if 0 <= index < ACTIVITY_HOURS:
            activity.setdefault(channel, [0] * ACTIVITY_HOURS)[index] += int(count)
    fresh = await _counts_since(db, ids, since) if since is not None else None
    reads = []
    for row in rows:
        count, newest = totals.get(row.mm_channel_id, (0, None))
        reads.append(
            ChannelRead(
                mm_channel_id=row.mm_channel_id,
                name=row.name,
                display_name=row.display_name,
                team_name=row.team_name,
                channel_type=row.channel_type,
                status="closed" if row.closed else "open",
                archived=row.archived,
                accessible=row.accessible,
                following=row.following,
                is_new=not row.reviewed,
                pulled=is_pulled(row),
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
                closed_at=row.closed_at,
                message_count=int(count),
                last_message_at=newest,
                activity=activity.get(row.mm_channel_id, [0] * ACTIVITY_HOURS),
                new_since=None if fresh is None else fresh.get(row.mm_channel_id, 0),
            )
        )
    return reads


def _sweep_read() -> SweepRead:
    return SweepRead(
        configured=configured(),
        last_at=SWEEP_STATE.last_at,
        ok=SWEEP_STATE.ok,
        problem=SWEEP_STATE.problem,
        bot=SWEEP_STATE.bot,
        interval_seconds=get_settings().mattermost_interval_seconds,
    )


@router.get("/channels")
async def list_channels(
    db: DbSession, _current_user: CurrentUser, since: AwareDatetime | None = None
) -> ChannelsResponse:
    """Every channel the sweeps have found, open ones first, by name; with `since`, a time with
    its zone, each with how many of its messages arrived after it."""
    rows = (await db.execute(select(MattermostChannel))).scalars().all()
    ordered = sorted(rows, key=lambda row: (row.closed, (row.display_name or row.name).lower()))
    reads = await _channel_reads(db, ordered, since)
    return ChannelsResponse(channels=reads, sweep=_sweep_read())


async def _audit_channel(
    db: AsyncSession,
    request: Request,
    user: User,
    action_type: str,
    entity_id: str | None,
    detail: dict[str, Any],
) -> None:
    await write_audit(
        db,
        action_type=action_type,
        entity_type="mattermost_channel",
        entity_id=entity_id,
        user_id=user.id,
        ip_address=client_ip(request),
        detail=detail,
    )
    await db.commit()


@router.patch("/channels/{channel_id}")
async def update_channel(
    channel_id: ChannelId,
    payload: ChannelUpdate,
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> ChannelRead:
    """Follow or unfollow a channel, or mark it reviewed. A closed channel cannot be followed:
    Holly pulls nothing more from it."""
    row = (
        await db.execute(
            select(MattermostChannel).where(MattermostChannel.mm_channel_id == channel_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    if payload.following and row.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This channel is closed: Holly pulls nothing more from it.",
        )
    changes: dict[str, Any] = {}
    if payload.following is not None and payload.following != row.following:
        changes["following"] = {"from": row.following, "to": payload.following}
        row.following = payload.following
        row.following_changed_at = datetime.now(UTC)
        row.following_changed_by = user.id
    if payload.reviewed and not row.reviewed:
        changes["reviewed"] = True
        row.reviewed = True
    if changes:
        detail = {"channel": row.display_name or row.name, **changes}
        await _audit_channel(db, request, user, AUDIT_CHANNEL_UPDATE, row.mm_channel_id, detail)
    [read] = await _channel_reads(db, [row])
    return read


@router.post("/channels/reviewed")
async def review_all_channels(
    request: Request, db: DbSession, user: CurrentUser
) -> ReviewedResponse:
    """Mark every new channel reviewed."""
    rows = (
        (await db.execute(select(MattermostChannel).where(MattermostChannel.reviewed.is_(False))))
        .scalars()
        .all()
    )
    for row in rows:
        row.reviewed = True
    if rows:
        names = sorted(row.display_name or row.name for row in rows)
        detail = {"count": len(rows), "channels": names}
        await _audit_channel(db, request, user, AUDIT_CHANNEL_REVIEW, None, detail)
    return ReviewedResponse(reviewed=len(rows))


@router.post("/sweep")
async def sweep_now(request: Request, user: CurrentUser) -> SweepResponse:
    """Find the bot's channels and pull the followed open ones now, rather than at the next
    cycle. A call made while a cycle runs joins it."""
    MATTERMOST_SWEEP_LIMIT.check(str(user.id))
    tally = await run_mattermost_now(user.id, client_ip(request))
    sweep = tally.sweep or SweepResult()
    return SweepResponse(
        ok=SWEEP_STATE.ok,
        problem=SWEEP_STATE.problem,
        found=sweep.found,
        new=sweep.new,
        closed=sweep.closed,
        reopened=sweep.reopened,
        lost=sweep.lost,
        channels_polled=tally.channels_polled,
        channels_failed=tally.channels_failed,
        inserted=tally.inserted,
    )
