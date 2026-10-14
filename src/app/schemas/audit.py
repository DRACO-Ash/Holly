from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    timestamp: datetime
    user_id: UUID | None = None
    action_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    ip_address: str | None = None
    detail: str | None = None
    previous_hash: str | None = None
    entry_hash: str


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int
