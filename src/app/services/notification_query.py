"""Read-time deduplication for notification queries.

UDL re-publishes the same logical notice many times: each publication arrives with its own
UDL `id` and lands as its own row in `notification` (the ingest unique constraint is on
`udl_id`, which keeps every UDL payload). Operator-facing views want one row per logical
notice: the latest version.

Grouping key, in order of preference:
  1. event_id (UDL Event_Id; stable across re-publications)
  2. notso_identifier (the NOTSO ticket number)
  3. udl_id (the fallback, so a row with neither grouping field passes through as itself
     rather than being merged with others arbitrarily)

`Notification.created_at` breaks ties within a group when udl_created_at is equal or missing.
"""

from collections.abc import Iterable
from typing import Any

from sqlalchemy import ColumnElement, Subquery, func
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select, select

from app.models.notification import Notification


def notification_group_key() -> ColumnElement[str]:
    """The SQL expression that groups many UDL records into one logical notice."""
    return func.coalesce(
        Notification.event_id,
        Notification.notso_identifier,
        Notification.udl_id,
    )


def deduped_notifications_select(
    conditions: Iterable[ColumnElement[bool]] | None = None,
) -> Select[Notification]:
    """A SELECT yielding the latest Notification row per logical notice.

    PostgreSQL DISTINCT ON: the ORDER BY leads with the grouping key, then the freshness
    columns. Wrap it in a subquery before applying a user's sort or paging.
    """
    group_key = notification_group_key()
    stmt = select(Notification)
    if conditions:
        stmt = stmt.where(*conditions)
    return stmt.ext(distinct_on(group_key)).order_by(
        group_key,
        Notification.udl_created_at.desc().nullslast(),
        Notification.created_at.desc(),
    )


def aliased_deduped_notifications(
    conditions: Iterable[ColumnElement[bool]] | None = None,
) -> tuple[Any, Subquery]:
    """(alias, subquery): use the alias for the outer query's columns and ORDER BY, and the
    subquery for COUNT."""
    subquery = deduped_notifications_select(conditions).subquery()
    alias: Any = aliased(Notification, subquery)
    return alias, subquery
