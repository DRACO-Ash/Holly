"""Each object's story, told from what Holly already holds.

An object is a catalogue number a notice in the window names: in its satellite list, its single
`sat_no`, or in brackets in its event class (an RPO's second object is often only there). Its
story is every publication of those notices, the providers' maneuver records, the chat threads a
mission lead has confirmed are about them, the timers set against them and the analysts' notes.

Holly also suggests threads: posts in followed channels that mention one of the object's NOTSO
numbers, or its catalogue number as a whole number. A suggestion is only that until a lead
confirms it. Nothing here calls the assistant or sends anything outside Holly.
"""

import re
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.like import contains_pattern
from app.models.event_timer import EventTimer
from app.models.handover import CONFIRMED, HandoverNote, HandoverThreadLink
from app.models.maneuver import Maneuver
from app.models.mattermost_channel import MattermostChannel
from app.models.mattermost_message import MattermostMessage
from app.models.notification import Notification
from app.models.user import User
from app.schemas.handover import (
    HandoverObject,
    StoryManeuver,
    StoryNote,
    StoryNotice,
    StoryPost,
    StoryThread,
    StoryTimer,
    ThreadSuggestion,
)
from app.schemas.maneuver import ManeuverFacts
from app.services.handover.taxonomy import parse_event_class
from app.services.maneuver_facts import fact_text, maneuver_facts
from app.services.notification_query import compute_event_key

OBJECT_NOTICE_CAP = 1000
STORY_NOTICE_CAP = 500
STORY_MANEUVER_CAP = 300
CANDIDATE_POST_CAP = 500
THREAD_CAP = 20
POSTS_PER_THREAD = 100
SUGGESTION_CAP = 20
NOTE_CAP = 200
TIMER_CAP = 100
# A NOTSO number shorter than this matches too much chat to be a useful suggestion.
_MIN_NOTICE_ID = 4
_NOTICE_ID_CAP = 20
_DIGITS = re.compile(r"\d{1,9}")
_POST_CAP = 4000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _catalogue(value: object) -> int | None:
    text = fact_text(value, 32)
    if text is not None and text.isascii() and _DIGITS.fullmatch(text):
        return int(text)
    return None


def catalogue_numbers(notice: Notification) -> dict[int, str | None]:
    """The objects a notice names, each with the name its event class gives, if any."""
    found: dict[int, str | None] = {}
    ids = notice.sat_ids if isinstance(notice.sat_ids, list) else []
    for number in (_catalogue(v) for v in ids[:50]):
        if number is not None:
            found.setdefault(number, None)
    if notice.sat_no is not None:
        found.setdefault(notice.sat_no, None)
    parsed = parse_event_class(fact_text(notice.event_class, 500))
    for obj in parsed.objects if parsed else ():
        if obj.catalogue_number is not None:
            found[obj.catalogue_number] = found.get(obj.catalogue_number) or obj.name
    return found


def kind_of(notice: Notification) -> str | None:
    parsed = parse_event_class(fact_text(notice.event_class, 500))
    return parsed.kind_label if parsed else None


@dataclass
class _Tally:
    name: str | None = None
    kinds: set[str] = field(default_factory=set)
    latest_at: datetime | None = None
    events: int = 0


def tally_objects(notices: Iterable[Notification]) -> dict[int, _Tally]:
    tallies: dict[int, _Tally] = {}
    for notice in notices:
        kind = kind_of(notice)
        for number, name in catalogue_numbers(notice).items():
            tally = tallies.setdefault(number, _Tally())
            tally.name = tally.name or name
            tally.events += 1
            if kind:
                tally.kinds.add(kind)
            when = notice.udl_created_at
            if when is not None and (tally.latest_at is None or when > tally.latest_at):
                tally.latest_at = when
    return tallies


def objects_from(tallies: dict[int, _Tally], maneuvers: dict[int, int]) -> list[HandoverObject]:
    objects = [
        HandoverObject(
            sat_no=number,
            name=t.name,
            kinds=sorted(t.kinds),
            latest_at=t.latest_at,
            events=t.events,
            maneuvers=maneuvers.get(number, 0),
        )
        for number, t in tallies.items()
    ]
    # Newest first; an object whose notices carry no time goes last.
    objects.sort(key=lambda o: (o.latest_at or _EPOCH, o.sat_no), reverse=True)
    return objects


def written_forms(sat_no: int) -> list[str]:
    """The catalogue number as a notice may write it: as it is, or zero-padded to nine digits."""
    plain = str(sat_no)
    return [plain.zfill(width) for width in range(len(plain), 10)]


def names_object(sat_no: int) -> ColumnElement[bool]:
    """A notice that may name the object: the database's coarse cut, which `names` confirms."""
    forms = written_forms(sat_no)
    return or_(
        Notification.sat_no == sat_no,
        *(Notification.sat_ids.contains([form]) for form in forms),
        *(Notification.event_class.like(f"%({form})%") for form in forms),
    )


def names(notice: Notification, sat_no: int) -> bool:
    """True when the notice names the object as the object list reads it."""
    return sat_no in catalogue_numbers(notice)


def story_notice(notice: Notification) -> StoryNotice:
    return StoryNotice(
        id=notice.id,
        event_key=compute_event_key(notice),
        notice=notice.notso_identifier or notice.notice_id,
        event_class=notice.event_class,
        kind=kind_of(notice),
        status=notice.status,
        udl_created_at=notice.udl_created_at,
        source=notice.source,
        udl_id=notice.udl_id,
    )


def story_maneuver(row: Maneuver) -> StoryManeuver:
    return StoryManeuver(
        id=row.id,
        source=row.source,
        event_start_time=row.event_start_time,
        maneuver_status=row.maneuver_status,
        udl_id=row.udl_id,
        facts=ManeuverFacts(**maneuver_facts(row.raw)),
    )


def thread_key() -> ColumnElement[str]:
    """A post's thread: its root post's id, or its own when it is the root."""
    return func.coalesce(MattermostMessage.root_id, MattermostMessage.mm_post_id)


def in_threads(thread_ids: Sequence[str]) -> ColumnElement[bool]:
    """Posts of these threads, written so the root_id and post id indexes serve it."""
    return or_(
        MattermostMessage.root_id.in_(thread_ids),
        and_(MattermostMessage.root_id.is_(None), MattermostMessage.mm_post_id.in_(thread_ids)),
    )


def _thread_of(post: MattermostMessage) -> str:
    return post.root_id or post.mm_post_id


def story_post(post: MattermostMessage) -> StoryPost:
    return StoryPost(
        post_id=post.mm_post_id,
        posted_at=post.posted_at,
        author=post.user_display_name,
        message=post.message[:_POST_CAP],
    )


def not_switched_off() -> ColumnElement[bool]:
    """Leaves out posts from a channel someone has switched off on the Comms page."""
    switched_off = (
        select(MattermostChannel.mm_channel_id)
        .where(
            MattermostChannel.mm_channel_id == MattermostMessage.channel_id,
            MattermostChannel.following.is_(False),
        )
        .exists()
    )
    return ~switched_off


@dataclass(frozen=True)
class Mentions:
    """What a post must mention to be suggested: a NOTSO number (to that notice's event), or
    the catalogue number (to the object's latest event)."""

    sat_no: int
    notice_ids: dict[str, str]  # NOTSO number, lower case, to its event key
    latest_event: str | None

    def condition(self) -> ColumnElement[bool]:
        clauses: list[ColumnElement[bool]] = [
            MattermostMessage.message.op("~")(rf"(^|[^0-9]){self.sat_no}([^0-9]|$)")
        ]
        clauses += [
            MattermostMessage.message.ilike(contains_pattern(notice_id), escape="\\")
            for notice_id in self.notice_ids
        ]
        return or_(*clauses)

    def match(self, text: str) -> tuple[str, str] | None:
        """(event key, reason) for a post, or None when it mentions nothing of the object."""
        lowered = text.lower()
        for notice_id, event_key in self.notice_ids.items():
            if notice_id in lowered:
                return event_key, f"Mentions NOTSO {notice_id.upper()}"
        if self.latest_event and re.search(rf"(?<!\d){self.sat_no}(?!\d)", text):
            return self.latest_event, f"Mentions catalogue number {self.sat_no}"
        return None


def mentions_for(sat_no: int, notices: Sequence[Notification]) -> Mentions:
    ids: dict[str, str] = {}
    for notice in reversed(notices):  # newest first, so the newest event keeps a shared id
        for value in (notice.notso_identifier, notice.notice_id):
            text = fact_text(value, 100)
            if text and len(text) >= _MIN_NOTICE_ID and len(ids) < _NOTICE_ID_CAP:
                ids.setdefault(text.lower(), compute_event_key(notice))
    latest = compute_event_key(notices[-1]) if notices else None
    return Mentions(sat_no=sat_no, notice_ids=ids, latest_event=latest)


def suggestions_from(
    posts: Sequence[MattermostMessage],
    mentions: Mentions,
    decided_threads: set[str],
) -> list[ThreadSuggestion]:
    """One suggestion per undecided thread, from its earliest matching post; one more than the
    cap at most, so the caller can tell the list was cut."""
    found: dict[str, ThreadSuggestion] = {}
    for post in sorted(posts, key=lambda p: p.posted_at):
        thread = _thread_of(post)
        if thread in decided_threads:
            continue
        if thread in found:
            found[thread].matching_posts += 1
            continue
        hit = mentions.match(post.message)
        if hit is None or len(found) > SUGGESTION_CAP:
            continue
        found[thread] = ThreadSuggestion(
            thread_id=thread,
            event_key=hit[0],
            channel_name=post.channel_name,
            reason=hit[1],
            first_post=story_post(post),
            matching_posts=1,
        )
    return list(found.values())


def threads_from(
    links: Sequence[HandoverThreadLink], posts: Sequence[MattermostMessage]
) -> list[StoryThread]:
    """One thread per confirmed thread id, however many of the object's notices it was
    confirmed against, newest decision first. A thread none of whose posts were read (its
    channel switched off, or its posts gone) is left out."""
    by_thread: dict[str, list[MattermostMessage]] = {}
    for post in posts:
        by_thread.setdefault(_thread_of(post), []).append(post)
    decided: dict[str, list[HandoverThreadLink]] = {}
    for link in links:
        if link.decision == CONFIRMED:
            decided.setdefault(link.thread_id, []).append(link)
    threads = []
    for thread_id, its_links in decided.items():
        held = sorted(by_thread.get(thread_id, []), key=lambda p: p.posted_at)
        if not held:
            continue
        threads.append(
            StoryThread(
                thread_id=thread_id,
                event_keys=sorted({ln.event_key for ln in its_links}),
                channel_name=held[0].channel_name,
                confirmed_at=max(ln.decided_at for ln in its_links),
                posts=[story_post(p) for p in held[:POSTS_PER_THREAD]],
                truncated=len(held) > POSTS_PER_THREAD,
            )
        )
    threads.sort(key=lambda t: t.confirmed_at, reverse=True)
    return threads


def newest_confirmed(links: Sequence[HandoverThreadLink]) -> tuple[list[str], bool]:
    """The confirmed thread ids to read, newest decision first, and whether the cap cut any."""
    latest: dict[str, datetime] = {}
    for link in links:
        if link.decision == CONFIRMED:
            latest[link.thread_id] = max(
                link.decided_at, latest.get(link.thread_id, link.decided_at)
            )
    ordered = sorted(latest, key=lambda t: latest[t], reverse=True)
    return ordered[:THREAD_CAP], len(ordered) > THREAD_CAP


def story_timer(timer: EventTimer) -> StoryTimer:
    return StoryTimer(
        id=timer.id, label=timer.label, target_time=timer.target_time, event_key=timer.event_key
    )


def story_notes(notes: Sequence[HandoverNote], authors: dict[uuid.UUID, str]) -> list[StoryNote]:
    return [
        StoryNote(
            id=n.id,
            author_id=n.author_id,
            author=authors.get(n.author_id) if n.author_id else None,
            text=n.text,
            created_at=n.created_at,
        )
        for n in notes
    ]


async def author_names(db: AsyncSession, notes: Sequence[HandoverNote]) -> dict[uuid.UUID, str]:
    ids = {n.author_id for n in notes if n.author_id is not None}
    if not ids:
        return {}
    rows = (await db.execute(select(User.id, User.username).where(User.id.in_(ids)))).all()
    return {row[0]: row[1] for row in rows}
