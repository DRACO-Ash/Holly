from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import StorableText, UDLEnvelopeRead


class NotificationRead(UDLEnvelopeRead):
    msg_type: str | None = None

    notso_identifier: str | None = None
    notice_id: str | None = None
    event_id: str | None = None

    event_class: str | None = None
    event_type: str | None = None
    status: str | None = None

    subject: str | None = None
    description: str | None = None
    region: str | None = None
    notso_link: str | None = None
    company_name: str | None = None

    publish_date: datetime | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    sat_no: int | None = None
    sat_ids: list[str] | None = None

    created_at: datetime
    updated_at: datetime


class NotificationDetail(NotificationRead):
    raw: dict[str, Any]


class NotificationPage(BaseModel):
    items: list[NotificationRead]
    total: int
    limit: int
    offset: int


class NotificationIngestRequest(BaseModel):
    msg_type: StorableText | None = "TACREP_NOTSO"
    created_at_gte: datetime | None = None
    data_mode: StorableText | None = None
    source: StorableText | None = None
    # Holly's own cap on what one manual pull may ask for. A request that names no limit asks
    # for none, and UDL applies its own default page size (TBC, re-verify: its value).
    max_results: int | None = Field(default=None, ge=1, le=10_000)


class NotificationIngestResponse(BaseModel):
    pulled: int
    inserted: int
    updated: int
    skipped: int
