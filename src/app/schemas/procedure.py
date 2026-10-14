from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcedureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    filename: str
    content_type: str
    size_bytes: int
    file_hash: str
    uploaded_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ProcedureContent(ProcedureRead):
    """Procedure metadata plus inlined file content for previewable types."""

    content: str | None = None
    content_truncated: bool = False


class ProcedurePage(BaseModel):
    items: list[ProcedureRead]
    total: int
