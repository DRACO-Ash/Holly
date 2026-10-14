"""Operator countdown timers, with a pre-alert and optional daily, weekly or monthly recurrence."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.common import get_or_404
from app.core.net import client_ip
from app.dependencies import CurrentUser, DbSession
from app.models.event_timer import EventTimer
from app.models.user import User
from app.schemas.event_timer import EventTimerCreate, EventTimerList, EventTimerRead
from app.services.audit import write_audit

router = APIRouter(prefix="/event-timers", tags=["event-timers"])

# Dismissed timers leave the active list after this long: long enough that an operator
# scrolling back through a shift still sees what was acknowledged, short enough that the list
# stays uncluttered across shifts.
_INCLUDE_DISMISSED_WINDOW = timedelta(hours=12)

# n steps of each recurrence. relativedelta keeps month ends: 31 January plus one month is 28
# or 29 February, and plus two months is 31 March.
_STEPS: dict[str, Callable[[int], timedelta | relativedelta]] = {
    "daily": lambda n: timedelta(days=n),
    "weekly": lambda n: timedelta(weeks=n),
    "monthly": lambda n: relativedelta(months=n),
}


def _whole_steps(anchor: datetime, moment: datetime, recurrence: str) -> int:
    """A count of steps from `anchor` that never passes `moment`, so the search below starts
    close to the answer instead of walking every occurrence since the anchor."""
    if moment <= anchor:
        return 0
    if recurrence == "monthly":
        return (moment.year - anchor.year) * 12 + moment.month - anchor.month - 1
    unit = timedelta(weeks=1) if recurrence == "weekly" else timedelta(days=1)
    return (moment - anchor) // unit


def _next_occurrence(anchor: datetime, after: datetime, recurrence: str) -> datetime:
    """The first occurrence later than `after`, counted in whole steps from `anchor`.

    Counting from the anchor, never from the last occurrence, keeps a monthly timer on its own
    day: one set for the 31st fires on 28 February and then on 31 March again.
    """
    step = _STEPS[recurrence]
    n = max(1, _whole_steps(anchor, after, recurrence))
    while anchor + step(n) <= after:
        n += 1
    return anchor + step(n)


async def _audit_timer(
    db: AsyncSession,
    request: Request,
    user: User,
    action_type: str,
    timer_id: UUID,
    detail: dict[str, Any],
) -> None:
    await write_audit(
        db,
        action_type=action_type,
        entity_type="event_timer",
        entity_id=str(timer_id),
        user_id=user.id,
        ip_address=client_ip(request),
        detail=detail,
    )


def _roll_forward(timer: EventTimer) -> tuple[str, dict[str, Any]]:
    """Move a recurring timer to its next occurrence; it stays active, with a fresh pre-alert.

    Dismissing acknowledges the current occurrence, so the next one is after both now and the
    current target: an operator who dismisses long after the alarm started (a daily 0900 timer
    dismissed at 1100 the next morning) rolls to an occurrence still to come.
    """
    previous_target = timer.target_time
    # Timers created before the anchor existed count from their current target.
    anchor = timer.recurrence_anchor or timer.target_time
    after = max(datetime.now(UTC), timer.target_time)
    timer.target_time = _next_occurrence(anchor, after, timer.recurrence)
    timer.recurrence_anchor = anchor
    timer.pre_alert_fired_at = None
    return "event_timer.roll_forward", {
        "label": timer.label,
        "recurrence": timer.recurrence,
        "previous_target": previous_target.isoformat(),
        "next_target": timer.target_time.isoformat(),
    }


def _dismiss(timer: EventTimer, user: User) -> tuple[str, dict[str, Any]]:
    now = datetime.now(UTC)
    timer.dismissed_at = now
    timer.dismissed_by = user.id
    if timer.pre_alert_fired_at is None:
        timer.pre_alert_fired_at = now
    return "event_timer.dismiss", {
        "label": timer.label,
        "target_time": timer.target_time.isoformat(),
    }


@router.get("")
async def list_active_timers(
    db: DbSession, _current_user: CurrentUser, include_dismissed: bool = False
) -> EventTimerList:
    stmt = select(EventTimer).order_by(EventTimer.target_time.asc())
    if not include_dismissed:
        cutoff = datetime.now(UTC) - _INCLUDE_DISMISSED_WINDOW
        stmt = stmt.where(
            or_(
                EventTimer.dismissed_at.is_(None),
                EventTimer.dismissed_at >= cutoff,
            )
        )
    items = (await db.execute(stmt)).scalars().all()
    return EventTimerList(items=[EventTimerRead.model_validate(t) for t in items])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_timer(
    payload: EventTimerCreate, request: Request, db: DbSession, current_user: CurrentUser
) -> EventTimerRead:
    target = payload.target_time
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    timer = EventTimer(
        event_key=payload.event_key,
        label=payload.label.strip(),
        target_time=target,
        recurrence_anchor=target,
        pre_alert_minutes=payload.pre_alert_minutes,
        recurrence=payload.recurrence,
        shift_date=payload.shift_date,
        created_by=current_user.id,
    )
    db.add(timer)
    await db.flush()
    await _audit_timer(
        db,
        request,
        current_user,
        "event_timer.create",
        timer.id,
        {
            "label": timer.label,
            "event_key": timer.event_key,
            "target_time": timer.target_time.isoformat(),
            "pre_alert_minutes": timer.pre_alert_minutes,
            "recurrence": timer.recurrence,
        },
    )
    await db.commit()
    await db.refresh(timer)
    return EventTimerRead.model_validate(timer)


@router.post("/{timer_id}/acknowledge-pre-alert")
async def acknowledge_pre_alert(
    timer_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> EventTimerRead:
    timer: EventTimer = await get_or_404(db, EventTimer, timer_id, "Timer")
    if timer.pre_alert_fired_at is None:
        timer.pre_alert_fired_at = datetime.now(UTC)
        await db.flush()
        await _audit_timer(
            db,
            request,
            current_user,
            "event_timer.acknowledge_pre_alert",
            timer.id,
            {"label": timer.label},
        )
        await db.commit()
        await db.refresh(timer)
    return EventTimerRead.model_validate(timer)


@router.post("/{timer_id}/dismiss")
async def dismiss_timer(
    timer_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> EventTimerRead:
    timer: EventTimer = await get_or_404(db, EventTimer, timer_id, "Timer")
    if timer.dismissed_at is None:
        # Only a known recurrence rolls forward; anything else, a value written outside the API
        # included, is dismissed once, so a bad row can never stall the worker in a loop.
        if timer.recurrence in _STEPS:
            action_type, detail = _roll_forward(timer)
        else:
            action_type, detail = _dismiss(timer, current_user)
        await db.flush()
        await _audit_timer(db, request, current_user, action_type, timer.id, detail)
        await db.commit()
        await db.refresh(timer)
    return EventTimerRead.model_validate(timer)


@router.delete("/{timer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timer(
    timer_id: UUID, request: Request, db: DbSession, current_user: CurrentUser
) -> None:
    timer: EventTimer = await get_or_404(db, EventTimer, timer_id, "Timer")
    label = timer.label
    await db.delete(timer)
    await _audit_timer(db, request, current_user, "event_timer.delete", timer_id, {"label": label})
    await db.commit()
