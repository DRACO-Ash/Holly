from datetime import datetime
from operator import eq, ge, le
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.v1.common import Limit, Offset, fetch_page, present_filters
from app.dependencies import DbSession, require_role
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit import AuditLogPage, AuditLogRead
from app.schemas.common import StorableText

router = APIRouter(prefix="/audit", tags=["audit"])

OperatorOrAdmin = Annotated[User, Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN))]


@router.get("")
async def list_audit_log(
    db: DbSession,
    _current_user: OperatorOrAdmin,
    action_type: StorableText | None = None,
    user_id: UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> AuditLogPage:
    base = select(AuditLog).where(
        *present_filters(
            [
                (action_type, AuditLog.action_type, eq),
                (user_id, AuditLog.user_id, eq),
                (since, AuditLog.timestamp, ge),
                (until, AuditLog.timestamp, le),
            ]
        )
    )
    items, total = await fetch_page(db, base, [AuditLog.timestamp.desc()], limit, offset)
    return AuditLogPage(
        items=[AuditLogRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
