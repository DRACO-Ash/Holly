"""Sweep the bot's Mattermost channels, then pull the followed open ones and store their posts.

Each cycle first sweeps the channels the bot can read (services/mattermost_channels.py), which
decides the channels to pull: followed, open and still readable. Strategy per channel:
1. Find the most recent `posted_at` already stored for that channel.
2. Ask Mattermost for posts since that high-water mark plus 1 ms, or for the last 24 hours on
   the first run.
3. Insert by `mm_post_id`; a post already stored is ignored.
4. System messages (type starting `system_`), empty posts, and posts whose id, timestamp or
   shape is malformed are skipped and counted. Mattermost's data is validated here, at the
   boundary, so one bad post can never abort a run or stall every later run at the same post.

User and channel display names are looked up once per ingest cycle and cached, so a burst of
messages does not call `/users/{id}` for every post.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.mattermost_message import MattermostMessage
from app.services.audit import write_audit
from app.services.mattermost_channels import (
    SWEEP_STATE,
    SweepResult,
    channels_to_pull,
    sweep_channels,
)
from app.services.mattermost_client import (
    NOT_CONFIGURED,
    PLAIN_ID,
    MattermostAuthError,
    MattermostClient,
    MattermostClientError,
    datetime_to_ms,
    ms_to_datetime,
)

logger = logging.getLogger(__name__)

_FIRST_RUN_WINDOW = timedelta(hours=24)
# Column limits (models/mattermost_message.py): longer names are cut, never refused.
_NAME_LENGTH = 200
_POST_TYPE_LENGTH = 50
# Timestamps outside the years 1970 to 9999 (epoch milliseconds) are malformed.
_LATEST_MS = 253_402_300_799_999


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _display_name(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if name := _text(record.get(key)):
            return name[:_NAME_LENGTH]
    return None


def _posted_at(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= _LATEST_MS:
        return None
    return ms_to_datetime(value)


@dataclass
class MattermostIngestResult:
    channels_polled: int = 0
    channels_failed: int = 0
    pulled: int = 0
    inserted: int = 0
    skipped: int = 0
    # The cycle's channel sweep; None when none ran or it failed.
    sweep: SweepResult | None = None


@dataclass
class _NameCache:
    users: dict[str, str | None] = field(default_factory=dict)
    channels: dict[str, str | None] = field(default_factory=dict)

    async def user_display_name(self, client: MattermostClient, user_id: str) -> str | None:
        if not user_id:
            return None
        if user_id not in self.users:
            try:
                user = await client.get_user(user_id)
                self.users[user_id] = _display_name(user, "nickname", "username")
            except MattermostClientError:
                self.users[user_id] = None
        return self.users[user_id]

    async def channel_name(self, client: MattermostClient, channel_id: str) -> str | None:
        if channel_id not in self.channels:
            try:
                channel = await client.get_channel(channel_id)
                self.channels[channel_id] = _display_name(channel, "display_name", "name")
            except MattermostClientError:
                self.channels[channel_id] = None
        return self.channels[channel_id]


async def _since_ms(db: AsyncSession, channel_id: str) -> int:
    stmt = select(func.max(MattermostMessage.posted_at)).where(
        MattermostMessage.channel_id == channel_id
    )
    high_water: datetime | None = (await db.execute(stmt)).scalar_one_or_none()
    if high_water is None:
        return datetime_to_ms(datetime.now(UTC) - _FIRST_RUN_WINDOW)
    # 1 ms past the newest stored post, so the boundary post is not pulled again.
    return datetime_to_ms(high_water) + 1


async def _row_for_post(
    client: MattermostClient,
    channel_id: str,
    channel_name: str | None,
    post: object,
    names: _NameCache,
) -> dict[str, Any] | None:
    """The row to store for one post, or None to skip it."""
    if not isinstance(post, dict):
        return None
    post_id = _text(post.get("id"))
    post_type = _text(post.get("type"))
    text = _text(post.get("message"))
    posted_at = _posted_at(post.get("create_at"))
    if (
        not PLAIN_ID.fullmatch(post_id)
        or post_type.startswith("system_")
        or posted_at is None
        or not text.strip()
    ):
        return None
    # An author id that is missing or malformed is stored empty and never looked up.
    user_id = _text(post.get("user_id"))
    if not PLAIN_ID.fullmatch(user_id):
        user_id = ""
    return {
        "mm_post_id": post_id,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "user_id": user_id,
        "user_display_name": await names.user_display_name(client, user_id),
        "posted_at": posted_at,
        "message": text,
        "post_type": post_type[:_POST_TYPE_LENGTH] or None,
        "raw": post,
    }


async def _fetch_posts(
    client: MattermostClient, channel_id: str, since_ms: int
) -> tuple[dict[str, Any], list[Any]] | None:
    """One channel's posts keyed by id, and their ids newest first; None when the channel
    cannot be read or the answer is not in Mattermost's shape."""
    try:
        payload = await client.get_channel_posts_since(channel_id, since_ms)
    except MattermostClientError as exc:
        # An auth error (the bot is not in the channel) is a MattermostClientError too.
        verb = "skipped" if isinstance(exc, MattermostAuthError) else "failed"
        logger.warning("Mattermost channel %s %s: %s", channel_id, verb, exc)
        return None
    posts = payload.get("posts") or {}
    order = payload.get("order") or []
    if not isinstance(posts, dict) or not isinstance(order, list):
        logger.warning(
            "Mattermost channel %s failed: the posts were not in the expected shape", channel_id
        )
        return None
    return posts, order


async def _ingest_channel(
    db: AsyncSession,
    client: MattermostClient,
    channel_id: str,
    names: _NameCache,
    tally: MattermostIngestResult,
) -> None:
    page = await _fetch_posts(client, channel_id, await _since_ms(db, channel_id))
    if page is None:
        tally.channels_failed += 1
        return
    posts, order = page
    tally.channels_polled += 1
    tally.pulled += len(order)
    if not order:
        return
    channel_name = await names.channel_name(client, channel_id)
    rows = []
    for post_id in order:
        post = posts.get(post_id) if isinstance(post_id, str) else None
        row = await _row_for_post(client, channel_id, channel_name, post, names)
        if row is None:
            tally.skipped += 1
        else:
            rows.append(row)
    tally.inserted += await _store(db, rows)


async def _store(db: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Insert the rows, leaving any post already held, and return how many were added."""
    if not rows:
        return 0
    stmt = pg_insert(MattermostMessage).values(rows)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_mattermost_message_post_id")
    result = cast(CursorResult[Any], await db.execute(stmt))
    return result.rowcount or 0


def _configured() -> bool:
    settings = get_settings()
    return bool(settings.mattermost_url and settings.mattermost_bot_token.get_secret_value())


def _audit_detail(tally: MattermostIngestResult) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "channels_polled": tally.channels_polled,
        "channels_failed": tally.channels_failed,
        "pulled": tally.pulled,
        "inserted": tally.inserted,
        "skipped": tally.skipped,
    }
    if tally.sweep is not None:
        detail["sweep"] = {
            "found": tally.sweep.found,
            "new": tally.sweep.new,
            "closed": tally.sweep.closed,
            "reopened": tally.sweep.reopened,
            "lost": tally.sweep.lost,
        }
    return detail


def _changed(sweep: SweepResult | None) -> bool:
    return sweep is not None and bool(sweep.new or sweep.closed or sweep.reopened or sweep.lost)


async def ingest_mattermost_messages(
    db: AsyncSession,
    *,
    channel_ids: list[str] | None = None,
    user_id_actor: Any = None,
    ip_address: str | None = None,
) -> MattermostIngestResult:
    """Sweep the channels and pull the ones to pull, or pull `channel_ids` alone, unswept."""
    tally = MattermostIngestResult()
    if not _configured():
        SWEEP_STATE.ok = False
        SWEEP_STATE.problem = NOT_CONFIGURED
        return tally

    channels: dict[str, str | None] = dict.fromkeys(channel_ids or [])
    try:
        async with MattermostClient() as client:
            if channel_ids is None:
                tally.sweep = await sweep_channels(db, client)
                channels = await channels_to_pull(db)
            names = _NameCache(channels={k: v for k, v in channels.items() if v is not None})
            for channel_id in channels:
                await _ingest_channel(db, client, channel_id, names, tally)
    except MattermostClientError as exc:
        logger.warning("Mattermost ingest aborted: %s", exc)
        tally.channels_failed = len(channels) - tally.channels_polled

    audited = bool(tally.channels_polled or tally.channels_failed or _changed(tally.sweep))
    if audited:
        await write_audit(
            db,
            action_type="mattermost.ingest",
            entity_type="mattermost_ingest_run",
            user_id=user_id_actor,
            ip_address=ip_address,
            detail=_audit_detail(tally),
        )
    # A sweep's own changes, such as when each channel was last seen, are kept even when nothing
    # new arrived.
    if audited or tally.sweep is not None:
        await db.commit()
    return tally
