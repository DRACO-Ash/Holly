"""Find the Mattermost channels the bot can read, and decide which of them Holly pulls (ADR-015).

Each sweep lists the bot's teams, then its channels in each team, archived ones included, and
keeps the public ("O") and private ("P") ones: a direct or group message is never Holly's to
read. Every value Mattermost sends is checked here, at the boundary, so one malformed record is
skipped rather than stopping the sweep.

● A channel found for the first time is followed at once, so no channel the bot joins is missed,
  and stays new until someone reviews it on the Comms page. On the very first sweep, a channel
  already named in MATTERMOST_CHANNEL_IDS arrives reviewed: that list was the old way of choosing.
● A channel whose name or display name holds the word CLOSED, in any case, or that is archived,
  is closed: Holly keeps what it pulled and pulls nothing more. Should the word go, it reopens.
● A channel a complete sweep no longer finds is marked inaccessible and is not pulled. A sweep
  that fails part-way changes nothing of the kind.

Until a sweep has succeeded once, Holly pulls the channels MATTERMOST_CHANNEL_IDS names, as
before; afterwards the table decides. The outcome of the latest sweep is kept in this process,
for the Comms page, never Mattermost's own words.
"""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.storable import storable_text
from app.models.mattermost_channel import MattermostChannel
from app.services.mattermost_client import PLAIN_ID, MattermostClient, MattermostClientError

logger = logging.getLogger(__name__)

# The word CLOSED, in any case, with no letter either side: "CLOSED - Op Falcon" and
# "op-falcon-closed" are closed; "Disclosed reports" is not.
CLOSED_WORD = re.compile(r"(?<![a-z])closed(?![a-z])", re.IGNORECASE)
# Mattermost's types for a public and a private channel; "D" and "G" are direct and group messages.
PULLED_TYPES = frozenset({"O", "P"})
# Column limits (models/mattermost_channel.py): longer names are cut, never refused.
_NAME_LENGTH = 200
_BOT_NAME_LENGTH = 64


@dataclass
class SweepResult:
    found: int = 0
    new: int = 0
    closed: int = 0
    reopened: int = 0
    lost: int = 0
    skipped: int = 0


@dataclass
class SweepState:
    """The latest sweep's outcome in this process: when it ran, whether it succeeded, a fixed
    message when it did not, and the bot's username."""

    last_at: datetime | None = None
    ok: bool | None = None
    problem: str | None = None
    bot: str | None = None


SWEEP_STATE = SweepState()


def forget_sweep() -> None:
    """Forget the latest sweep's outcome (used by tests)."""
    SWEEP_STATE.last_at = SWEEP_STATE.ok = SWEEP_STATE.problem = SWEEP_STATE.bot = None


@dataclass(frozen=True)
class FoundChannel:
    mm_channel_id: str
    team_id: str
    team_name: str | None
    name: str
    display_name: str | None
    channel_type: str
    archived: bool


def _clean(value: object, limit: int = _NAME_LENGTH) -> str | None:
    """A name Holly can store and show: text, cut to `limit`, printable; None otherwise."""
    if not isinstance(value, str):
        return None
    text = value.strip()[:limit]
    if not text or not storable_text(text) or not text.isprintable():
        return None
    return text


def is_closed(name: str, display_name: str | None, archived: bool) -> bool:
    return archived or any(CLOSED_WORD.search(text) for text in (name, display_name or ""))


def found_channel(record: object, team_id: str, team_name: str | None) -> FoundChannel | None:
    """The channel a record from Mattermost describes, or None to skip it."""
    if not isinstance(record, dict):
        return None
    channel_id = record.get("id")
    kind = record.get("type")
    name = _clean(record.get("name"))
    if not (isinstance(channel_id, str) and PLAIN_ID.fullmatch(channel_id)) or name is None:
        return None
    if kind not in PULLED_TYPES:
        return None
    delete_at = record.get("delete_at")
    archived = isinstance(delete_at, int) and not isinstance(delete_at, bool) and delete_at > 0
    return FoundChannel(
        mm_channel_id=channel_id,
        team_id=team_id,
        team_name=team_name,
        name=name,
        display_name=_clean(record.get("display_name")),
        channel_type=str(kind),
        archived=archived,
    )


def _team(record: object) -> tuple[str, str | None] | None:
    """A team's id and the name it is shown by, or None to skip it."""
    if not isinstance(record, dict):
        return None
    team_id = record.get("id")
    if not (isinstance(team_id, str) and PLAIN_ID.fullmatch(team_id)):
        return None
    return team_id, _clean(record.get("display_name")) or _clean(record.get("name"))


def _conversation(record: object) -> bool:
    # Direct and group messages are left out by design, not counted as malformed.
    return isinstance(record, dict) and record.get("type") in {"D", "G"}


async def list_bot_channels(client: MattermostClient) -> tuple[list[FoundChannel], int]:
    """Every public and private channel the bot is in, across its teams, and how many records
    were skipped. Raises MattermostClientError when any listing fails, so a partial answer is
    never taken for the whole."""
    found: dict[str, FoundChannel] = {}
    skipped = 0
    for record in await client.get_my_teams():
        team = _team(record)
        if team is None:
            skipped += 1
            continue
        for item in await client.get_my_team_channels(team[0]):
            channel = found_channel(item, *team)
            if channel is not None:
                found[channel.mm_channel_id] = channel
            elif not _conversation(item):
                skipped += 1
    return list(found.values()), skipped


def seed_channel_ids() -> set[str]:
    """The channels MATTERMOST_CHANNEL_IDS names: the old fixed list, now a seed."""
    raw = get_settings().mattermost_channel_ids or ""
    return {part.strip() for part in raw.split(",") if PLAIN_ID.fullmatch(part.strip())}


def _apply(row: MattermostChannel, channel: FoundChannel, now: datetime) -> None:
    row.team_id = channel.team_id
    row.team_name = channel.team_name
    row.name = channel.name
    row.display_name = channel.display_name
    row.channel_type = channel.channel_type
    row.archived = channel.archived
    row.accessible = True
    row.last_seen_at = now


def _new_row(
    channel: FoundChannel, reviewed: bool, closed: bool, now: datetime
) -> MattermostChannel:
    """A channel found for the first time: followed at once, new unless the seed named it."""
    return MattermostChannel(
        mm_channel_id=channel.mm_channel_id,
        following=True,
        reviewed=reviewed,
        first_seen_at=now,
        closed=closed,
        closed_at=now if closed else None,
    )


def _note_closing(row: MattermostChannel, closed: bool, now: datetime, result: SweepResult) -> None:
    """Count a known channel that closed or reopened since the last sweep, and when it closed."""
    if closed and not row.closed:
        result.closed += 1
        row.closed_at = now
    elif not closed and row.closed:
        result.reopened += 1
        row.closed_at = None


async def record_sweep(
    db: AsyncSession, channels: list[FoundChannel], now: datetime | None = None
) -> SweepResult:
    """Bring the channel table up to a complete sweep's findings; flushed, not committed."""
    now = now or datetime.now(UTC)
    known = {
        row.mm_channel_id: row
        for row in (await db.execute(select(MattermostChannel))).scalars().all()
    }
    seeded = seed_channel_ids() if not known else set()
    result = SweepResult(found=len(channels))
    for channel in channels:
        closed = is_closed(channel.name, channel.display_name, channel.archived)
        row = known.pop(channel.mm_channel_id, None)
        if row is None:
            row = _new_row(channel, channel.mm_channel_id in seeded, closed, now)
            db.add(row)
            result.new += 0 if row.reviewed else 1
        else:
            _note_closing(row, closed, now, result)
        row.closed = closed
        _apply(row, channel, now)
    for row in known.values():
        if row.accessible:
            result.lost += 1
            row.accessible = False
    await db.flush()
    return result


async def sweep_channels(db: AsyncSession, client: MattermostClient) -> SweepResult | None:
    """Run one sweep and record its outcome in SWEEP_STATE; None when it failed, which leaves
    the table as it was."""
    now = datetime.now(UTC)
    SWEEP_STATE.last_at = now
    try:
        if SWEEP_STATE.bot is None:
            SWEEP_STATE.bot = _clean((await client.get_me()).get("username"), _BOT_NAME_LENGTH)
        channels, skipped = await list_bot_channels(client)
    except MattermostClientError as exc:
        SWEEP_STATE.ok = False
        SWEEP_STATE.problem = _problem(exc)
        logger.warning("Mattermost channel sweep failed: %s", SWEEP_STATE.problem)
        return None
    result = await record_sweep(db, channels, now)
    result.skipped = skipped
    SWEEP_STATE.ok = True
    SWEEP_STATE.problem = None
    return result


def _problem(exc: MattermostClientError) -> str:
    # Holly's own short message (services/api_client.py), never Mattermost's response body.
    return str(exc)


async def channels_to_pull(db: AsyncSession) -> dict[str, str | None]:
    """The channels to pull now, followed, open and readable, with the name each is shown by.
    Until a sweep has succeeded once the table is empty, and MATTERMOST_CHANNEL_IDS decides."""
    rows = (await db.execute(select(MattermostChannel))).scalars().all()
    if not rows:
        return dict.fromkeys(sorted(seed_channel_ids()))
    pulled = (row for row in rows if row.following and not row.closed and row.accessible)
    return {
        row.mm_channel_id: row.display_name or row.name
        for row in sorted(pulled, key=lambda row: row.mm_channel_id)
    }
