from datetime import datetime
from operator import eq, ge, le
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.v1.common import (
    Limit,
    Offset,
    SortDirection,
    fetch_page,
    get_or_404,
    present_filters,
    sort_order,
)
from app.dependencies import CurrentUser, DbSession
from app.models.maneuver import Maneuver
from app.schemas.maneuver import ManeuverDetail, ManeuverPage, ManeuverRead

router = APIRouter(prefix="/maneuvers", tags=["maneuvers"])

ManeuverSortColumn = Literal[
    "sat_no",
    "event_start_time",
    "event_stop_time",
    "mnvr_type",
    "udl_created_at",
    "created_at",
]


@router.get("")
async def list_maneuvers(
    db: DbSession,
    _current_user: CurrentUser,
    sat_no: int | None = None,
    mnvr_type: str | None = None,
    event_start_time_gte: datetime | None = None,
    event_start_time_lte: datetime | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
    sort_by: ManeuverSortColumn = "event_start_time",
    sort_dir: SortDirection = "desc",
) -> ManeuverPage:
    base = select(Maneuver).where(
        *present_filters(
            [
                (sat_no, Maneuver.sat_no, eq),
                (mnvr_type, Maneuver.mnvr_type, eq),
                (event_start_time_gte, Maneuver.event_start_time, ge),
                (event_start_time_lte, Maneuver.event_start_time, le),
            ]
        )
    )
    order = [sort_order(getattr(Maneuver, sort_by), sort_dir), Maneuver.created_at.desc()]
    items, total = await fetch_page(db, base, order, limit, offset)
    return ManeuverPage(
        items=[ManeuverRead.model_validate(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{maneuver_id}")
async def get_maneuver(
    maneuver_id: UUID, db: DbSession, _current_user: CurrentUser
) -> ManeuverDetail:
    return ManeuverDetail.model_validate(await get_or_404(db, Maneuver, maneuver_id, "Maneuver"))
