"""What the API routes share: paging, optional filters, sorting, counting, fetch-or-404, and
the answer to a failed upstream call."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated, Any, Literal

from fastapi import HTTPException, Query, status
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.services.udl_client import UDLClient, UDLClientError
from app.services.udl_records import IngestResult

Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]
SortDirection = Literal["asc", "desc"]


# A comparison such as operator.eq, operator.ge or operator.le, applied as compare(column, value).
Comparison = Callable[[Any, Any], ColumnElement[bool]]


def present_filters(
    candidates: Sequence[tuple[object | None, Any, Comparison]],
) -> list[ColumnElement[bool]]:
    """The filter clauses for the query values that were supplied, in order.

    Each clause is built only when its value is present: comparing a column with None by >= or
    <= is an error in SQLAlchemy, not an empty filter.
    """
    return [compare(column, value) for value, column, compare in candidates if value is not None]


def sort_order(column: InstrumentedAttribute[Any], direction: SortDirection) -> ColumnElement[Any]:
    """The column in the requested direction, with nulls last either way."""
    ordered = column.asc() if direction == "asc" else column.desc()
    return ordered.nullslast()


async def fetch_page(
    db: AsyncSession,
    base: Select[Any],
    order_by: Sequence[ColumnElement[Any]],
    limit: int,
    offset: int,
) -> tuple[Sequence[Any], int]:
    """One page of `base`, in order, and the total number of rows it matches."""
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    page = base.order_by(*order_by).limit(limit).offset(offset)
    items = (await db.execute(page)).scalars().all()
    return items, total


async def get_or_404(db: AsyncSession, model: Any, item_id: object, label: str) -> Any:
    """The row of `model` with this id, or a 404 naming what was not found."""
    row = (await db.execute(select(model).where(model.id == item_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return row


def bad_gateway(exc: Exception) -> HTTPException:
    """502 for a failed upstream call. The message is Holly's own (the clients keep upstream
    response bodies in the server log), so it is safe to return."""
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


async def run_udl_ingest(ingest: Callable[[UDLClient], Awaitable[IngestResult]]) -> IngestResult:
    """Open a UDL client, run one ingest with it, and answer 502 when UDL fails."""
    try:
        async with UDLClient() as client:
            return await ingest(client)
    except UDLClientError as exc:
        raise bad_gateway(exc) from exc
