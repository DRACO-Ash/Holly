from dataclasses import asdict
from datetime import datetime
from operator import eq, ge, le
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
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
from app.dependencies import CurrentUser, DbSession
from app.models.elset import Elset
from app.schemas.elset import (
    ElsetDetail,
    ElsetIngestRequest,
    ElsetIngestResponse,
    ElsetPage,
    ElsetRead,
)
from app.services.elset_ingest import ingest_elsets

router = APIRouter(prefix="/elsets", tags=["elsets"])

ElsetSortColumn = Literal[
    "sat_no", "epoch", "mean_motion", "eccentricity", "inclination", "source", "created_at"
]


@router.get("")
async def list_elsets(
    db: DbSession,
    _current_user: CurrentUser,
    sat_no: int | None = None,
    epoch_gte: datetime | None = None,
    epoch_lte: datetime | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
    sort_by: ElsetSortColumn = "epoch",
    sort_dir: SortDirection = "desc",
) -> ElsetPage:
    base = select(Elset).where(
        *present_filters(
            [
                (sat_no, Elset.sat_no, eq),
                (epoch_gte, Elset.epoch, ge),
                (epoch_lte, Elset.epoch, le),
            ]
        )
    )
    order = [sort_order(getattr(Elset, sort_by), sort_dir)]
    items, total = await fetch_page(db, base, order, limit, offset)
    return ElsetPage(
        items=[ElsetRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{elset_id}")
async def get_elset(elset_id: UUID, db: DbSession, _current_user: CurrentUser) -> ElsetDetail:
    return ElsetDetail.model_validate(await get_or_404(db, Elset, elset_id, "Elset"))


@router.post("/ingest")
async def trigger_ingest(
    payload: ElsetIngestRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> ElsetIngestResponse:
    result = await run_udl_ingest(
        lambda client: ingest_elsets(
            db,
            client,
            epoch_gte=payload.epoch_gte,
            sat_no=payload.sat_no,
            max_results=payload.max_results,
            user_id=current_user.id,
            ip_address=client_ip(request),
        )
    )
    return ElsetIngestResponse(**asdict(result))
