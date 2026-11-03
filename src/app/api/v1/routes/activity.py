"""The activity overview the console views draw: one window of notices (one row per logical
notice, with its urgency), the maneuvers that started in it, and the latest element set of each
satellite either names. Reading only; signed-in users only.

Each list is capped, newest first, and the answer says when a cap was reached, so a view never
presents part of a window as the whole of it.
"""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on

from app.config import get_settings
from app.dependencies import CurrentUser, DbSession
from app.models.assistant_evaluation import AssistantEvaluation
from app.models.elset import Elset
from app.models.maneuver import Maneuver
from app.models.notification import Notification
from app.schemas.activity import (
    ActivityElset,
    ActivityManeuver,
    ActivityNotice,
    ActivityOverview,
    ActivityTruncated,
)
from app.schemas.maneuver import ManeuverFacts
from app.services.feed_rollup import latest_by_notification, rollup_urgency
from app.services.maneuver_facts import fact_text, maneuver_facts
from app.services.notification_query import aliased_deduped_notifications

router = APIRouter(prefix="/activity", tags=["activity"])

NOTICE_CAP = 1000
MANEUVER_CAP = 2000
ELSET_CAP = 2000
# A NORAD catalogue number, as a notice's satellite list carries it: digits only, nine at most.
_SAT_ID_DIGITS = 9
# A satellite id is a catalogue number or a short designation; nothing longer is one.
SAT_ID_CAP = 32


def _sat_ids(notification: Any) -> list[str]:
    ids = notification.sat_ids if isinstance(notification.sat_ids, list) else []
    kept = [text for text in (fact_text(value, SAT_ID_CAP) for value in ids) if text is not None]
    if not kept and notification.sat_no is not None:
        kept = [str(notification.sat_no)]
    return kept[:50]


def _catalogue_number(sat_id: str) -> int | None:
    digits = sat_id.strip()
    if digits.isascii() and digits.isdigit() and len(digits) <= _SAT_ID_DIGITS:
        return int(digits)
    return None


def _capped(rows: Sequence[Any], cap: int) -> tuple[list[Any], bool]:
    return list(rows[:cap]), len(rows) > cap


def _notice(notification: Any, evaluation: AssistantEvaluation | None) -> ActivityNotice:
    urgency, top_action = rollup_urgency(evaluation)
    return ActivityNotice(
        id=notification.id,
        notice=notification.notso_identifier or notification.notice_id,
        event_class=notification.event_class,
        event_type=notification.event_type,
        status=notification.status,
        region=notification.region,
        udl_created_at=notification.udl_created_at,
        sat_ids=_sat_ids(notification),
        urgency=urgency,
        top_action=top_action,
    )


def _maneuver(row: Maneuver) -> ActivityManeuver:
    return ActivityManeuver(
        id=row.id,
        sat_no=row.sat_no,
        source=row.source,
        event_start_time=row.event_start_time,
        event_stop_time=row.event_stop_time,
        mnvr_type=row.mnvr_type,
        maneuver_status=row.maneuver_status,
        delta_v=row.delta_v,
        facts=ManeuverFacts(**maneuver_facts(row.raw)),
    )


def _satellites(
    notices: Iterable[ActivityNotice], maneuvers: Iterable[ActivityManeuver]
) -> set[int]:
    numbers = {m.sat_no for m in maneuvers if m.sat_no is not None}
    for notice in notices:
        numbers.update(n for n in map(_catalogue_number, notice.sat_ids) if n is not None)
    return numbers


@router.get("")
async def activity(
    db: DbSession,
    _current_user: CurrentUser,
    hours: Annotated[int | None, Query(ge=1, le=336)] = None,
) -> ActivityOverview:
    window_hours = hours or get_settings().background_notification_window_hours
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=window_hours)

    notification, _subquery = aliased_deduped_notifications(
        [Notification.udl_created_at >= window_start]
    )
    notice_stmt = (
        select(notification)
        .order_by(notification.udl_created_at.desc(), notification.created_at.desc())
        .limit(NOTICE_CAP + 1)
    )
    notice_rows, notices_cut = _capped((await db.execute(notice_stmt)).scalars().all(), NOTICE_CAP)
    latest: dict[Any, AssistantEvaluation] = {}
    if notice_rows:
        eval_stmt = select(AssistantEvaluation).where(
            AssistantEvaluation.notification_id.in_([n.id for n in notice_rows])
        )
        latest = latest_by_notification((await db.execute(eval_stmt)).scalars().all())
    notices = [_notice(n, latest.get(n.id)) for n in notice_rows]

    maneuver_stmt = (
        select(Maneuver)
        .where(Maneuver.event_start_time >= window_start)
        .order_by(Maneuver.event_start_time.desc(), Maneuver.created_at.desc())
        .limit(MANEUVER_CAP + 1)
    )
    maneuver_rows, maneuvers_cut = _capped(
        (await db.execute(maneuver_stmt)).scalars().all(), MANEUVER_CAP
    )
    maneuvers = [_maneuver(m) for m in maneuver_rows]

    satellites = sorted(_satellites(notices, maneuvers))
    wanted, elsets_cut = satellites[:ELSET_CAP], len(satellites) > ELSET_CAP
    elsets: list[ActivityElset] = []
    if wanted:
        elset_stmt = (
            select(Elset)
            .where(Elset.sat_no.in_(wanted))
            .ext(distinct_on(Elset.sat_no))
            .order_by(Elset.sat_no, Elset.epoch.desc())
        )
        elsets = [
            ActivityElset.model_validate(e) for e in (await db.execute(elset_stmt)).scalars().all()
        ]

    return ActivityOverview(
        window_hours=window_hours,
        window_start=window_start,
        generated_at=now,
        notices=notices,
        maneuvers=maneuvers,
        elsets=elsets,
        truncated=ActivityTruncated(
            notices=notices_cut, maneuvers=maneuvers_cut, elsets=elsets_cut
        ),
    )
