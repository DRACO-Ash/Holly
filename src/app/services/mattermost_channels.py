"""Find the Mattermost channels the bot can read, and decide which of them Holly pulls (ADR-015).

Each sweep lists the bot's teams, then its channels in each team, archived ones included, and
keeps the public ("O") and private ("P") ones: a direct or group message is never Holly's to
read. Every value Mattermost sends is checked here, at the boundary, so one malformed record is
skipped rather than stopping the sweep.

● A channel found for the first time is followed at once, so no channel the bot joins is missed,
  and stays new until someone reviews it on the Comms page. One found already closed arrives
  reviewed, since Holly pulls nothing from it. While the table is empty, so does one named in
  MATTERMOST_CHANNEL_IDS, the old way of choosing, and a seed the sweep does not find is
  logged. The first sweep follows every channel the bot is in, not only the seed.
● A channel whose name or display name holds the word CLOSED, in any case, or that is archived,
  is closed: Holly keeps what it pulled and pulls nothing more. Should the word go, it reopens.
● A channel a complete sweep no longer finds is marked inaccessible and is not pulled. A sweep
  that fails part-way, or that skipped a malformed record (which might be that channel), marks
  nothing lost. A bot in more than MAX_TEAMS teams or MAX_CHANNELS channels fails the sweep
  rather than store an unbounded list.

While the table is empty, Holly pulls the channels MATTERMOST_CHANNEL_IDS names, as before;
once a sweep has found a channel, the table decides. The outcome of the latest sweep is kept in
this process, for the Comms page, never Mattermost's own words.
"""

import logging
import re
import unicodedata
from collections.abc import Iterable
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
# The most a sweep takes in: beyond these the bot was added far wider than Holly is meant to read.
MAX_TEAMS = 100
MAX_CHANNELS = 1000
UNEXPECTED = "The channel sweep failed unexpectedly; the server log has the detail."


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
    # Decided from the names as Mattermost sent them (is_closed), before they are cleaned.
    closed: bool = False


def clean_name(value: object, limit: int = _NAME_LENGTH) -> str | None:
    """A name Holly can store and show: text, cut to `limit`, printable; None otherwise."""
    if not isinstance(value, str):
        return None
    text = value.strip()[:limit]
    if not text or not storable_text(text) or not text.isprintable():
        return None
    return text


# Characters a reader cannot see that Unicode files outside the categories dropped below: the
# combining grapheme joiner, the Hangul and Khmer fillers, the Mongolian and other variation
# selectors.
_INVISIBLE = frozenset(
    {0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x3164, 0xFFA0}
    | set(range(0x180B, 0x1810))
    | set(range(0xFE00, 0xFE10))
    | set(range(0xE0100, 0xE01F0))
)
# Format, combining, control and unassigned characters: none is a letter a reader sees in the
# word. Unassigned covers the default-ignorable code points Unicode reserves, which a browser
# draws as nothing, and any format or combining character newer than Python's Unicode data.
# Dropping a character can only join letters into the word, so it fails towards closed.
_DROPPED = frozenset({"Cf", "Mn", "Me", "Cc", "Cn"})


def _word_text(value: object) -> str:
    """A name as Mattermost sent it, read for the word CLOSED as a reader sees it: compatibility
    forms folded (fullwidth and styled letters become plain ones, by NFKC), and every invisible,
    combining or control character taken out, so none can split or hide the word; a space, a tab
    or a line break still parts two words. A combining accent folds into its letter, which is
    then another letter; one with no letter of its own, such as a diaeresis over the C, is dropped,
    so it closes. A letter from
    another script that only looks Latin, such as the Cyrillic Es, is not folded (SECURITY.md). A
    name that is not text, which Mattermost never sends, reads as empty."""
    if not isinstance(value, str):
        return ""
    folded = unicodedata.normalize("NFKC", value)
    return "".join(
        " " if char.isspace() else char
        for char in folded
        if char.isspace()
        or (unicodedata.category(char) not in _DROPPED and ord(char) not in _INVISIBLE)
    )


def is_closed(name: object, display_name: object, archived: bool) -> bool:
    """Closed when archived, or when either name holds the word CLOSED. The names are read as
    Mattermost sent them, before Holly cleans them to show: a name too odd to show, which Holly
    drops, still closes the channel."""
    return archived or any(CLOSED_WORD.search(_word_text(text)) for text in (name, display_name))


def found_channel(record: object, team_id: str, team_name: str | None) -> FoundChannel | None:
    """The channel a record from Mattermost describes, or None to skip it."""
    if not isinstance(record, dict):
        return None
    channel_id = record.get("id")
    kind = _kind(record)
    name = clean_name(record.get("name"))
    if not (isinstance(channel_id, str) and PLAIN_ID.fullmatch(channel_id)) or name is None:
        return None
    if kind not in PULLED_TYPES:
        return None
    delete_at = record.get("delete_at")
    # Any number but 0 or below marks it archived, a float and NaN too: a number Holly cannot
    # read as a time fails towards closed, never towards open.
    archived = (
        isinstance(delete_at, int | float)
        and not isinstance(delete_at, bool)
        and not delete_at <= 0
    )
    return FoundChannel(
        mm_channel_id=channel_id,
        team_id=team_id,
        team_name=team_name,
        name=name,
        display_name=clean_name(record.get("display_name")),
        channel_type=kind,
        archived=archived,
        closed=is_closed(record.get("name"), record.get("display_name"), archived),
    )


def _team(record: object) -> tuple[str, str | None] | None:
    """A team's id and the name it is shown by, or None to skip it."""
    if not isinstance(record, dict):
        return None
    team_id = record.get("id")
    if not (isinstance(team_id, str) and PLAIN_ID.fullmatch(team_id)):
        return None
    return team_id, clean_name(record.get("display_name")) or clean_name(record.get("name"))


def _kind(record: dict[str, object]) -> str:
    # Only a string is looked up in a set: a list or an object there would raise TypeError.
    kind = record.get("type")
    return kind if isinstance(kind, str) else ""


def _conversation(record: object) -> bool:
    # Direct and group messages are left out by design, not counted as malformed.
    return isinstance(record, dict) and _kind(record) in {"D", "G"}


def _too_many(what: str, limit: int) -> MattermostClientError:
    return MattermostClientError(f"The bot is in more than {limit} {what}; the sweep stopped.")


async def list_bot_channels(client: MattermostClient) -> tuple[list[FoundChannel], int]:
    """Every public and private channel the bot is in, across its teams, and how many records
    were skipped. Raises MattermostClientError when any listing fails, so a partial answer is
    never taken for the whole."""
    found: dict[str, FoundChannel] = {}
    skipped = 0
    teams = await client.get_my_teams()
    if len(teams) > MAX_TEAMS:
        raise _too_many("teams", MAX_TEAMS)
    for record in teams:
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
        if len(found) > MAX_CHANNELS:
            raise _too_many("channels", MAX_CHANNELS)
    return list(found.values()), skipped


def seed_channel_ids() -> set[str]:
    """The channels MATTERMOST_CHANNEL_IDS names: the old fixed list, now a seed."""
    raw = get_settings().mattermost_channel_ids or ""
    return {part.strip() for part in raw.split(",") if PLAIN_ID.fullmatch(part.strip())}


def is_pulled(row: MattermostChannel) -> bool:
    """Whether Holly pulls a channel: followed, open and still readable."""
    return row.following and not row.closed and row.accessible


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
    """A channel found for the first time: followed at once, new unless `reviewed`."""
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


def _note_missing_seeds(seeded: set[str], channels: list[FoundChannel]) -> None:
    missing = seeded - {channel.mm_channel_id for channel in channels}
    if missing:
        logger.warning(
            "The sweep did not find %s channel(s) MATTERMOST_CHANNEL_IDS names: %s",
            len(missing),
            ", ".join(sorted(missing)),
        )


def _mark_lost(rows: Iterable[MattermostChannel], result: SweepResult) -> None:
    """Mark each channel a complete sweep did not find as one the bot can no longer read."""
    for row in rows:
        if row.accessible:
            result.lost += 1
            row.accessible = False


async def record_sweep(
    db: AsyncSession,
    channels: list[FoundChannel],
    now: datetime | None = None,
    skipped: int = 0,
) -> SweepResult:
    """Bring the channel table up to a sweep's findings; flushed, not committed. With
    `skipped` records, no channel is marked lost: a skipped one might be it."""
    now = now or datetime.now(UTC)
    known = {
        row.mm_channel_id: row
        for row in (await db.execute(select(MattermostChannel))).scalars().all()
    }
    seeded = seed_channel_ids() if not known else set()
    _note_missing_seeds(seeded, channels)
    result = SweepResult(found=len(channels), skipped=skipped)
    for channel in channels:
        closed = channel.closed or channel.archived
        row = known.pop(channel.mm_channel_id, None)
        if row is None:
            row = _new_row(channel, closed or channel.mm_channel_id in seeded, closed, now)
            db.add(row)
            result.new += 0 if row.reviewed else 1
        else:
            _note_closing(row, closed, now, result)
        row.closed = closed
        _apply(row, channel, now)
    if not skipped:
        _mark_lost(known.values(), result)
    await db.flush()
    return result


async def sweep_channels(db: AsyncSession, client: MattermostClient) -> SweepResult | None:
    """Run one sweep and record its outcome in SWEEP_STATE; None when it failed, which leaves
    the table as it was."""
    now = datetime.now(UTC)
    SWEEP_STATE.last_at = now
    try:
        if SWEEP_STATE.bot is None:
            SWEEP_STATE.bot = clean_name((await client.get_me()).get("username"), _BOT_NAME_LENGTH)
        channels, skipped = await list_bot_channels(client)
        result = await record_sweep(db, channels, now, skipped)
    except MattermostClientError as exc:
        SWEEP_STATE.ok = False
        SWEEP_STATE.problem = _problem(exc)
        logger.warning("Mattermost channel sweep failed: %s", SWEEP_STATE.problem)
        return None
    except Exception:
        # Fail closed in Holly's words: nothing of the sweep is kept, and the page says it failed.
        await db.rollback()
        SWEEP_STATE.ok = False
        SWEEP_STATE.problem = UNEXPECTED
        logger.exception("Mattermost channel sweep crashed")
        return None
    if skipped:
        logger.warning(
            "The channel sweep skipped %s malformed record(s); none marked lost", skipped
        )
    SWEEP_STATE.ok = True
    SWEEP_STATE.problem = None
    return result


def _problem(exc: MattermostClientError) -> str:
    # Holly's own short message (services/api_client.py), never Mattermost's response body.
    return str(exc)


async def channels_to_pull(db: AsyncSession) -> dict[str, str | None]:
    """The channels to pull now, followed, open and readable, with the name each is shown by.
    While the table is empty, MATTERMOST_CHANNEL_IDS decides."""
    rows = (await db.execute(select(MattermostChannel))).scalars().all()
    if not rows:
        return dict.fromkeys(sorted(seed_channel_ids()))
    pulled = (row for row in rows if is_pulled(row))
    return {
        row.mm_channel_id: row.display_name or row.name
        for row in sorted(pulled, key=lambda row: row.mm_channel_id)
    }
