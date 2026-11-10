"""The Handover tab: the objects with live events, each object's story, the mission lead's
decisions on suggested chat threads, and analysts' notes. Signed-in users only; every write is
audited. Nothing here calls the assistant (tests/test_handover.py holds that line).
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.core.net import client_ip
from app.dependencies import CurrentUser, DbSession
from app.models.event_timer import EventTimer
from app.models.handover import CONFIRMED, HandoverNote, HandoverThreadLink
from app.models.maneuver import Maneuver
from app.models.mattermost_message import MattermostMessage
from app.models.notification import Notification
from app.schemas.handover import (
    HandoverNoteCreate,
    HandoverObjectList,
    HandoverStory,
    StoryNote,
    ThreadLinkDecision,
)
from app.services.audit import write_audit
from app.services.event_summary import compute_event_key
from app.services.handover import story as s
from app.services.notification_query import (
    aliased_deduped_notifications,
    notification_group_key,
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


async def _threads(
    db: DbSession, keys: set[str], mentions: s.Mentions, start: datetime
) -> tuple[list[Any], list[Any], bool]:
    links: list[HandoverThreadLink] = []
    if keys:
        link_stmt = select(HandoverThreadLink).where(HandoverThreadLink.event_key.in_(keys))
        links = list((await db.execute(link_stmt)).scalars().all())
    confirmed = sorted({ln.thread_id for ln in links if ln.decision == CONFIRMED})[: s.THREAD_CAP]
    posts: list[MattermostMessage] = []
    if confirmed:
        post_stmt = (
            select(MattermostMessage)
            .where(s.thread_key().in_(confirmed))
            .order_by(MattermostMessage.posted_at)
            .limit(s.THREAD_CAP * s.POSTS_PER_THREAD)
        )
        posts = list((await db.execute(post_stmt)).scalars().all())
    candidate_stmt = (
        select(MattermostMessage)
        .where(MattermostMessage.posted_at >= start, s.not_switched_off(), mentions.condition())
        .order_by(MattermostMessage.posted_at.desc())
        .limit(s.CANDIDATE_POST_CAP + 1)
    )
    candidates, cut = _capped(
        (await db.execute(candidate_stmt)).scalars().all(), s.CANDIDATE_POST_CAP
    )
    decided = {ln.thread_id for ln in links}
    shown_links = [ln for ln in links if ln.thread_id in confirmed]
    return (
        s.threads_from(shown_links, posts),
        s.suggestions_from(candidates, mentions, decided),
        cut,
    )


@router.get("/objects/{sat_no}")
async def object_story(
    sat_no: SatNo, db: DbSession, _current_user: CurrentUser, hours: Hours = None
) -> HandoverStory:
    window_hours, start, now = _window(hours)
    notice_stmt = (
        select(Notification)
        .where(Notification.udl_created_at >= start, s.names_object(sat_no))
        .order_by(Notification.udl_created_at, Notification.created_at)
        .limit(s.STORY_NOTICE_CAP + 1)
    )
    notices, notices_cut = _capped(
        (await db.execute(notice_stmt)).scalars().all(), s.STORY_NOTICE_CAP
    )
    maneuver_stmt = (
        select(Maneuver)
        .where(Maneuver.sat_no == sat_no, Maneuver.event_start_time >= start)
        .order_by(Maneuver.event_start_time)
        .limit(s.STORY_MANEUVER_CAP + 1)
    )
    maneuvers, maneuvers_cut = _capped(
        (await db.execute(maneuver_stmt)).scalars().all(), s.STORY_MANEUVER_CAP
    )
    keys = {compute_event_key(n) for n in notices}
    threads, suggestions, posts_cut = await _threads(
        db, keys, s.mentions_for(sat_no, notices), start
    )
    timers: list[EventTimer] = []
    if keys:
        timer_stmt = (
            select(EventTimer)
            .where(EventTimer.event_key.in_(keys), EventTimer.dismissed_at.is_(None))
            .order_by(EventTimer.target_time)
        )
        timers = list((await db.execute(timer_stmt)).scalars().all())
    note_stmt = (
        select(HandoverNote)
        .where(HandoverNote.sat_no == sat_no)
        .order_by(HandoverNote.created_at.desc())
        .limit(s.NOTE_CAP)
    )
    notes = list((await db.execute(note_stmt)).scalars().all())
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
        truncated=notices_cut or maneuvers_cut or posts_cut,
    )


@router.post("/thread-links")
async def decide_thread_link(
    payload: ThreadLinkDecision, request: Request, db: DbSession, current_user: CurrentUser
) -> ThreadLinkDecision:
    """Confirm or reject a suggested link, or clear an earlier decision. The notice and the
    thread must both be ones Holly holds."""
    event_key = payload.event_key.strip()
    notice = await db.execute(
        select(Notification.id).where(notification_group_key() == event_key).limit(1)
    )
    thread = await db.execute(
        select(MattermostMessage.id).where(s.thread_key() == payload.thread_id).limit(1)
    )
    if notice.scalar_one_or_none() is None or thread.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No such notice or thread.")
    if payload.decision == "clear":
        await db.execute(
            delete(HandoverThreadLink).where(
                HandoverThreadLink.thread_id == payload.thread_id,
                HandoverThreadLink.event_key == event_key,
            )
        )
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
