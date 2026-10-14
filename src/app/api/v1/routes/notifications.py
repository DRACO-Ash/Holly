from dataclasses import asdict
from datetime import datetime
from operator import eq, ge, le
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.api.v1.common import (
    Limit,
    Offset,
    SortDirection,
    fetch_page,
    get_or_404,
    present_filters,
    run_udl_ingest,
    sort_order,
)
from app.core.net import client_ip
from app.core.rate_limit import ASSISTANT_LIMIT
from app.dependencies import CurrentUser, DbSession
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationDetail,
    NotificationIngestRequest,
    NotificationIngestResponse,
    NotificationPage,
    NotificationRead,
)
from app.services.background_refresh import run_pull_notifications_now
from app.services.notification_ingest import ingest_notifications
from app.services.notification_query import aliased_deduped_notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])

NotificationSortColumn = Literal[
    "notso_identifier",
    "notice_id",
    "msg_type",
    "event_type",
    "status",
    "publish_date",
    "effective_from",
    "effective_until",
    "sat_no",
    "udl_created_at",
    "created_at",
]


@router.get("")
async def list_notifications(
    db: DbSession,
    _current_user: CurrentUser,
    msg_type: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    sat_no: int | None = None,
    effective_from_gte: datetime | None = None,
    effective_from_lte: datetime | None = None,
    created_at_gte: datetime | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
    sort_by: NotificationSortColumn = "udl_created_at",
    sort_dir: SortDirection = "desc",
) -> NotificationPage:
    conditions = present_filters(
        [
            (msg_type, Notification.msg_type, eq),
            (event_type, Notification.event_type, eq),
            (status, Notification.status, eq),
            (sat_no, Notification.sat_no, eq),
            (effective_from_gte, Notification.effective_from, ge),
            (effective_from_lte, Notification.effective_from, le),
            (created_at_gte, Notification.udl_created_at, ge),
        ]
    )
    # One row per logical notice: the latest UDL publication of each.
    notification, _subquery = aliased_deduped_notifications(conditions)
    order = [sort_order(getattr(notification, sort_by), sort_dir), notification.created_at.desc()]
    items, total = await fetch_page(db, select(notification), order, limit, offset)
    return NotificationPage(
        items=[NotificationRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{notification_id}")
async def get_notification(
    notification_id: UUID, db: DbSession, _current_user: CurrentUser
) -> NotificationDetail:
    row = await get_or_404(db, Notification, notification_id, "Notification")
    return NotificationDetail.model_validate(row)


@router.post("/ingest")
async def trigger_notification_ingest(
    payload: NotificationIngestRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> NotificationIngestResponse:
    result = await run_udl_ingest(
        lambda client: ingest_notifications(
            db,
            client,
            msg_type=payload.msg_type,
            created_at_gte=payload.created_at_gte,
            data_mode=payload.data_mode,
            source=payload.source,
            max_results=payload.max_results,
            user_id=current_user.id,
            ip_address=client_ip(request),
        )
    )
    return NotificationIngestResponse(**asdict(result))


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_notifications_now(current_user: CurrentUser) -> dict[str, str]:
    """Run the notification cycle now (UDL pull, auto-evaluate, event summaries) rather than
    waiting for the hourly cadence. It answers once the cycle completes, so the operator's
    next reload shows the fresh state; a refresh during a running cycle joins it. The cycle
    can call the assistant, so it counts against the caller's assistant limit."""
    ASSISTANT_LIMIT.check(str(current_user.id))
    await run_pull_notifications_now()
    return {"status": "complete"}
