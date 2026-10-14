"""UDL notifications: Tactical Reports and Notices to Space Operators (TACREP_NOTSO)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.services.udl_client import UDLClient
from app.services.udl_records import (
    ENVELOPE_FIELDS,
    IngestResult,
    Record,
    RecordStore,
    Row,
    copy_fields,
    set_datetime_if_present,
    set_first_present,
    set_int_if_present,
)

_ENVELOPE_TEXT_FIELDS = (("msgType", "msg_type"), *ENVELOPE_FIELDS)

# The TACREP_NOTSO msgBody, as (msgBody field, column). NOTSO and Event_Class each fill two
# columns: the notice identifier and id, and the event class and subject.
_MSG_BODY_FIELDS = (
    ("NOTSO", "notso_identifier"),
    ("NOTSO", "notice_id"),
    ("Event_Class", "event_class"),
    ("Event_Class", "subject"),
    ("Event_Type", "event_type"),
    ("Event_Id", "event_id"),
    ("Status", "status"),
    ("Event_Description", "description"),
    ("Company_Name", "company_name"),
    ("NOTSO_Link", "notso_link"),
)

# Flat-shaped fallbacks for other msgTypes on the same endpoint: the first present field fills
# the column, when the msgBody did not.
_FLAT_FALLBACKS = (
    ("notice_id", ("noticeId", "noticeNumber")),
    ("subject", ("subject",)),
    ("description", ("description", "text")),
)

UPDATABLE_COLUMNS: list[str] = [
    "msg_type",
    "data_mode",
    "source",
    "classification_marking",
    "created_by",
    "orig_network",
    "udl_created_at",
    "notso_identifier",
    "notice_id",
    "event_id",
    "event_class",
    "event_type",
    "status",
    "subject",
    "description",
    "region",
    "notso_link",
    "company_name",
    "publish_date",
    "effective_from",
    "effective_until",
    "sat_no",
    "sat_ids",
    "raw",
]


def _sat_ids(value: object) -> list[str]:
    """UDL's SatIds as text. UDL sends them as strings or numbers; anything else in the list is
    dropped, so every reader can treat them as text."""
    if not isinstance(value, list):
        return []
    return [str(sat) for sat in value if isinstance(sat, str | int) and not isinstance(sat, bool)]


def _map_msg_body(mapped: Row, msg_body: dict[str, Any]) -> None:
    copy_fields(mapped, msg_body, _MSG_BODY_FIELDS)
    set_datetime_if_present(mapped, "publish_date", msg_body.get("Publish_Date"))
    sat_ids = _sat_ids(msg_body.get("SatIds"))
    if sat_ids:
        mapped["sat_ids"] = sat_ids
        # A single-satellite notice also fills sat_no, so the existing filters and sorts work.
        if len(sat_ids) == 1:
            set_int_if_present(mapped, "sat_no", sat_ids[0])


def _map_udl_record(record: Record) -> Row | None:
    udl_id = record.get("id")
    if not udl_id:
        return None
    mapped: Row = {"udl_id": str(udl_id), "raw": record}
    copy_fields(mapped, record, _ENVELOPE_TEXT_FIELDS)
    set_datetime_if_present(mapped, "udl_created_at", record.get("createdAt"))
    msg_body = record.get("msgBody")
    if isinstance(msg_body, dict):
        _map_msg_body(mapped, msg_body)

    for column, keys in _FLAT_FALLBACKS:
        set_first_present(mapped, column, (record.get(key) for key in keys))
    copy_fields(mapped, record, (("region", "region"),))
    set_datetime_if_present(mapped, "effective_from", record.get("effectiveFrom"))
    for key in ("effectiveUntil", "expirationTime"):
        if "effective_until" not in mapped:
            set_datetime_if_present(mapped, "effective_until", record.get(key))
    if "sat_no" not in mapped:
        set_int_if_present(mapped, "sat_no", record.get("satNo"))
    return mapped


_STORE = RecordStore(
    Notification,
    _map_udl_record,
    constraint="uq_notification_udl_id",
    updatable=UPDATABLE_COLUMNS,
    audit=("udl.notification.ingest", "notification_ingest_run"),
)


async def ingest_notifications(
    db: AsyncSession,
    client: UDLClient,
    *,
    msg_type: str | None = None,
    created_at_gte: datetime | None = None,
    data_mode: str | None = None,
    source: str | None = None,
    max_results: int | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
) -> IngestResult:
    records = await client.get_notifications(
        msg_type=msg_type,
        created_at_gte=created_at_gte,
        data_mode=data_mode,
        source=source,
        max_results=max_results,
    )
    query = {
        "msg_type": msg_type,
        "created_at_gte": created_at_gte.isoformat() if created_at_gte else None,
        "data_mode": data_mode,
        "source": source,
        "max_results": max_results,
    }
    return await _STORE.ingest(db, records, query, user_id=user_id, ip_address=ip_address)
