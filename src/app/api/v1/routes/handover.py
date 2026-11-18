"""The Handover tab: the objects with live events, each object's story, the mission lead's
decisions on suggested chat threads, and analysts' notes; and the Object Lens's per-analyst watch
list and "last looked" times. Signed-in users only; every write that others can see is audited.
Nothing here calls the assistant (tests/test_handover.py holds that line).
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status
from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.core.net import client_ip
from app.dependencies import CurrentUser, DbSession
from app.models.event_timer import EventTimer
from app.models.handover import HandoverNote, HandoverThreadLink, ObjectWatch
from app.models.maneuver import Maneuver
from app.models.mattermost_message import MattermostMessage
from app.models.notification import Notification
from app.models.user import User
from app.schemas.handover import (
    HandoverNoteCreate,
    HandoverObjectList,
    HandoverStory,
    ObjectWatchList,
    ObjectWatchRead,
    StoryNote,
    ThreadLinkDecision,
    WatchUpdate,
)
from app.services.audit import write_audit
from app.services.handover import story as s
from app.services.notification_query import (
    aliased_deduped_notifications,
    compute_event_key,
)

router = APIRouter(prefix="/handover", tags=["handover"])

Hours = Annotated[int | None, Query(ge=1, le=336)]
SatNo = Annotated[int, Path(ge=1, le=999_999_999)]


def _window(hours: int | None) -> tuple[int, datetime, datetime]:
    window_hours = hours or get_settings().background_notification_window_hours
    now = datetime.now(UTC)
    return window_hours, now - timedelta(hours=window_hours), now


def _capped(rows: Any, cap: int) -> tuple[list[Any], bool]:
    rows = list(rows)
    return rows[:cap], len(rows) > cap


@router.get("/objects")
async def list_objects(
    db: DbSession, _current_user: CurrentUser, hours: Hours = None
) -> HandoverObjectList:
    window_hours, start, now = _window(hours)
    notice, _sub = aliased_deduped_notifications([Notification.udl_created_at >= start])
    stmt = select(notice).order_by(notice.udl_created_at.desc()).limit(s.OBJECT_NOTICE_CAP + 1)
    notices, cut = _capped((await db.execute(stmt)).scalars().all(), s.OBJECT_NOTICE_CAP)
    tallies = s.tally_objects(notices)
    counts: dict[int, int] = {}
    if tallies:
        count_stmt = (
            select(Maneuver.sat_no, func.count(Maneuver.id))
            .where(Maneuver.event_start_time >= start, Maneuver.sat_no.in_(list(tallies)))
            .group_by(Maneuver.sat_no)
        )
        rows = (await db.execute(count_stmt)).all()
        counts = {row[0]: row[1] for row in rows if row[0] is not None}
    return HandoverObjectList(
        window_hours=window_hours,
        window_start=start,
        generated_at=now,
        objects=s.objects_from(tallies, counts),
        truncated=cut,
    )


def _newest_kept(rows: Any, cap: int) -> tuple[list[Any], bool]:
    """Rows read newest first and one past the cap: the newest `cap`, oldest first, and
    whether any were left out."""
    rows = list(rows)
    return list(reversed(rows[:cap])), len(rows) > cap


async def _confirmed_posts(db: DbSession, thread_ids: list[str]) -> list[MattermostMessage]:
    """Up to one more post than a thread shows, per thread, oldest first, from channels not
    switched off; the extra one tells the thread it was cut."""
    rank = (
        func.row_number()
        .over(
            partition_by=s.thread_key(),
            order_by=(MattermostMessage.posted_at, MattermostMessage.mm_post_id),
        )
        .label("rank")
    )
    ranked = (
        select(MattermostMessage.id, rank)
        .where(s.in_threads(thread_ids), s.not_switched_off())
        .subquery()
    )
    stmt = (
        select(MattermostMessage)
        .join(ranked, ranked.c.id == MattermostMessage.id)
        .where(ranked.c.rank <= s.POSTS_PER_THREAD + 1)
        .order_by(MattermostMessage.posted_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _threads(
    db: DbSession, keys: set[str], mentions: s.Mentions, start: datetime
) -> tuple[list[Any], list[Any], bool]:
    links: list[HandoverThreadLink] = []
    if keys:
        link_stmt = select(HandoverThreadLink).where(HandoverThreadLink.event_key.in_(keys))
        links = list((await db.execute(link_stmt)).scalars().all())
    confirmed, threads_cut = s.newest_confirmed(links)
    posts = await _confirmed_posts(db, confirmed) if confirmed else []
    candidate_stmt = (
        select(MattermostMessage)
        .where(MattermostMessage.posted_at >= start, s.not_switched_off(), mentions.condition())
        .order_by(MattermostMessage.posted_at.desc())
        .limit(s.CANDIDATE_POST_CAP + 1)
    )
    candidates, candidates_cut = _capped(
        (await db.execute(candidate_stmt)).scalars().all(), s.CANDIDATE_POST_CAP
    )
    decided = {ln.thread_id for ln in links}
    shown = [ln for ln in links if ln.thread_id in confirmed]
    suggestions, suggestions_cut = _capped(
        s.suggestions_from(candidates, mentions, decided), s.SUGGESTION_CAP
    )
    threads = s.threads_from(shown, posts)
    cut = threads_cut or candidates_cut or suggestions_cut or any(t.truncated for t in threads)
    return threads, suggestions, cut


@router.get("/objects/{sat_no}")
async def object_story(
    sat_no: SatNo, db: DbSession, _current_user: CurrentUser, hours: Hours = None
) -> HandoverStory:
    """Everything Holly holds about one object in the window, oldest first. Over a cap the
    newest are kept and the answer says so."""
    window_hours, start, now = _window(hours)
    notice_stmt = (
        select(Notification)
        .where(Notification.udl_created_at >= start, s.names_object(sat_no))
        .order_by(Notification.udl_created_at.desc(), Notification.created_at.desc())
        .limit(s.STORY_NOTICE_CAP + 1)
    )
    read, notices_cut = _newest_kept(
        (await db.execute(notice_stmt)).scalars().all(), s.STORY_NOTICE_CAP
    )
    notices = [n for n in read if s.names(n, sat_no)]
    maneuver_stmt = (
        select(Maneuver)
        .where(Maneuver.sat_no == sat_no, Maneuver.event_start_time >= start)
        .order_by(Maneuver.event_start_time.desc())
        .limit(s.STORY_MANEUVER_CAP + 1)
    )
    maneuvers, maneuvers_cut = _newest_kept(
        (await db.execute(maneuver_stmt)).scalars().all(), s.STORY_MANEUVER_CAP
    )
    keys = {compute_event_key(n) for n in notices}
    threads, suggestions, threads_cut = await _threads(
        db, keys, s.mentions_for(sat_no, notices), start
    )
    timers: list[EventTimer] = []
    timers_cut = False
    if keys:
        timer_stmt = (
            select(EventTimer)
            .where(EventTimer.event_key.in_(keys), EventTimer.dismissed_at.is_(None))
            .order_by(EventTimer.target_time)
            .limit(s.TIMER_CAP + 1)
        )
        timers, timers_cut = _capped((await db.execute(timer_stmt)).scalars().all(), s.TIMER_CAP)
    note_stmt = (
        select(HandoverNote)
        .where(HandoverNote.sat_no == sat_no)
        .order_by(HandoverNote.created_at.desc())
        .limit(s.NOTE_CAP + 1)
    )
    notes, notes_cut = _capped((await db.execute(note_stmt)).scalars().all(), s.NOTE_CAP)
    names = {n: t.name for n, t in s.tally_objects(notices).items()}
    return HandoverStory(
        sat_no=sat_no,
        name=names.get(sat_no),
        window_hours=window_hours,
        window_start=start,
        generated_at=now,
        notices=[s.story_notice(n) for n in notices],
        maneuvers=[s.story_maneuver(m) for m in maneuvers],
        threads=threads,
        suggestions=suggestions,
        timers=[s.story_timer(t) for t in timers],
        notes=s.story_notes(notes, await s.author_names(db, notes)),
        truncated=notices_cut or maneuvers_cut or threads_cut or timers_cut or notes_cut,
    )


def _blank(column: Any) -> ColumnElement[bool]:
    return or_(column.is_(None), column == "")


def _has_key(event_key: str) -> ColumnElement[bool]:
    """Notices whose group key is this one, in the key's own order: event id, else NOTSO
    number, else UDL id, else the notice's own id."""
    no_event = _blank(Notification.event_id)
    no_notso = and_(no_event, _blank(Notification.notso_identifier))
    branches = [
        Notification.event_id == event_key,
        and_(no_event, Notification.notso_identifier == event_key),
        and_(no_notso, Notification.udl_id == event_key),
    ]
    try:
        own_id = UUID(event_key)
    except ValueError:
        return or_(*branches)
    if str(own_id) != event_key:
        return or_(*branches)
    return or_(*branches, and_(no_notso, _blank(Notification.udl_id), Notification.id == own_id))


async def _holds(db: DbSession, event_key: str, thread_id: str) -> bool:
    """True when Holly holds a notice with this group key and a post of this thread in a
    channel not switched off. The notice lookup follows the key's own order (event id, else
    NOTSO number, else UDL id, else its own id), so any row it finds has the key; Python
    confirms it."""
    notice_stmt = select(Notification).where(_has_key(event_key)).limit(1)
    held = (await db.execute(notice_stmt)).scalars().first()
    if held is None or compute_event_key(held) != event_key:
        return False
    thread_stmt = (
        select(MattermostMessage.id).where(s.in_threads([thread_id]), s.not_switched_off()).limit(1)
    )
    return (await db.execute(thread_stmt)).scalar_one_or_none() is not None


@router.post("/thread-links")
async def decide_thread_link(
    payload: ThreadLinkDecision, request: Request, db: DbSession, current_user: CurrentUser
) -> ThreadLinkDecision:
    """Confirm or reject a suggested link, or clear an earlier decision. To decide, the notice
    and a post of the thread in a channel not switched off must be ones Holly holds; clearing
    needs neither, so a decision can be undone after its notice or thread is gone."""
    event_key = payload.event_key
    if payload.decision == "clear":
        await db.execute(
            delete(HandoverThreadLink).where(
                HandoverThreadLink.thread_id == payload.thread_id,
                HandoverThreadLink.event_key == event_key,
            )
        )
    elif not await _holds(db, event_key, payload.thread_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such notice or thread.")
    else:
        now = datetime.now(UTC)
        values = {"decision": payload.decision, "decided_by": current_user.id, "decided_at": now}
        stmt = pg_insert(HandoverThreadLink).values(
            thread_id=payload.thread_id, event_key=event_key, **values
        )
        await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_handover_thread_link", set_={**values, "updated_at": now}
            )
        )
    await write_audit(
        db,
        action_type="handover.thread_link",
        entity_type="handover_thread_link",
        entity_id=payload.thread_id,
        user_id=current_user.id,
        ip_address=client_ip(request),
        detail={"event_key": event_key, "decision": payload.decision},
    )
    await db.commit()
    return ThreadLinkDecision(
        thread_id=payload.thread_id, event_key=event_key, decision=payload.decision
    )


@router.post("/objects/{sat_no}/notes", status_code=status.HTTP_201_CREATED)
async def add_note(
    sat_no: SatNo,
    payload: HandoverNoteCreate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> StoryNote:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Note text cannot be empty.")
    note = HandoverNote(id=uuid4(), sat_no=sat_no, author_id=current_user.id, text=text)
    db.add(note)
    await db.flush()
    await write_audit(
        db,
        action_type="handover.note.create",
        entity_type="handover_note",
        entity_id=str(note.id),
        user_id=current_user.id,
        ip_address=client_ip(request),
        detail={"sat_no": sat_no, "length": len(text)},
    )
    await db.commit()
    await db.refresh(note)
    return StoryNote(
        id=note.id,
        author_id=note.author_id,
        author=current_user.username,
        text=note.text,
        created_at=note.created_at,
    )


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> Response:
    note = (
        await db.execute(select(HandoverNote).where(HandoverNote.id == note_id))
    ).scalar_one_or_none()
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such note.")
    await db.delete(note)
    await write_audit(
        db,
        action_type="handover.note.delete",
        entity_type="handover_note",
        entity_id=str(note_id),
        user_id=current_user.id,
        ip_address=client_ip(request),
        detail={"sat_no": note.sat_no},
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# How many objects one analyst may keep on watch: enough for a shift's live events, few enough
# that the strip, and the stories it reads, stay small.
WATCH_CAP = 20
_WATCH_COLUMNS = (
    ObjectWatch.sat_no,
    ObjectWatch.pinned,
    ObjectWatch.pinned_at,
    ObjectWatch.last_seen_at,
)


def _watch_read(row: Any) -> ObjectWatchRead:
    return ObjectWatchRead(
        sat_no=row.sat_no, pinned=row.pinned, pinned_at=row.pinned_at, last_seen_at=row.last_seen_at
    )


@router.get("/watch")
async def list_watch(db: DbSession, current_user: CurrentUser) -> ObjectWatchList:
    """The analyst's own rows: objects on watch, in the order they were pinned, then those only
    looked at. Nobody else's."""
    stmt = (
        select(*_WATCH_COLUMNS)
        .where(ObjectWatch.user_id == current_user.id)
        .order_by(ObjectWatch.pinned.desc(), ObjectWatch.pinned_at, ObjectWatch.sat_no)
        .limit(500)
    )
    rows = (await db.execute(stmt)).all()
    return ObjectWatchList(items=[_watch_read(r) for r in rows], cap=WATCH_CAP)


@router.put("/watch/{sat_no}")
async def set_watch(
    sat_no: SatNo,
    payload: WatchUpdate,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ObjectWatchRead:
    """Put an object on the analyst's watch strip, or take it off. At most WATCH_CAP are on watch;
    the analyst's own row is locked first, so two pins at once cannot pass the cap together."""
    now = datetime.now(UTC)
    if payload.pinned:
        await db.execute(select(User.id).where(User.id == current_user.id).with_for_update())
        others = (
            await db.execute(
                select(func.count())
                .select_from(ObjectWatch)
                .where(
                    ObjectWatch.user_id == current_user.id,
                    ObjectWatch.pinned.is_(True),
                    ObjectWatch.sat_no != sat_no,
                )
            )
        ).scalar_one()
        if others >= WATCH_CAP:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"At most {WATCH_CAP} objects can be on watch. Take one off first.",
            )
    values = {"pinned": payload.pinned, "pinned_at": now if payload.pinned else None}
    stmt = (
        pg_insert(ObjectWatch)
        .values(id=uuid4(), user_id=current_user.id, sat_no=sat_no, **values)
        .on_conflict_do_update(
            constraint="uq_object_watch_user_sat", set_={**values, "updated_at": now}
        )
        .returning(*_WATCH_COLUMNS)
    )
    row = (await db.execute(stmt)).one()
    await write_audit(
        db,
        action_type="handover.watch",
        entity_type="object_watch",
        entity_id=str(sat_no),
        user_id=current_user.id,
        ip_address=client_ip(request),
        detail={"sat_no": sat_no, "pinned": payload.pinned},
    )
    await db.commit()
    return _watch_read(row)


@router.post("/watch/{sat_no}/seen")
async def mark_seen(sat_no: SatNo, db: DbSession, current_user: CurrentUser) -> ObjectWatchRead:
    """Record that the analyst has just looked at the object, so the lens marks only what is new
    after this. A private reading mark, like a read receipt nobody else sees, so it is not
    audited."""
    now = datetime.now(UTC)
    stmt = (
        pg_insert(ObjectWatch)
        .values(id=uuid4(), user_id=current_user.id, sat_no=sat_no, last_seen_at=now)
        .on_conflict_do_update(
            constraint="uq_object_watch_user_sat", set_={"last_seen_at": now, "updated_at": now}
        )
        .returning(*_WATCH_COLUMNS)
    )
    row = (await db.execute(stmt)).one()
    await db.commit()
    return _watch_read(row)
