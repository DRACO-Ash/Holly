"""Maneuver records pulled from UDL, as published by fusion providers."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.maneuver import Maneuver
from app.services.udl_client import UDLClient
from app.services.udl_records import (
    ENVELOPE_FIELDS,
    IngestResult,
    Record,
    RecordStore,
    Row,
    coerce_float,
    copy_fields,
    set_datetime_if_present,
    set_int_if_present,
    shared_filters,
)

_TEXT_FIELDS = (
    *ENVELOPE_FIELDS,
    ("origin", "origin"),
    ("mnvrType", "mnvr_type"),
    ("description", "description"),
    ("propulsionType", "propulsion_type"),
    ("maneuverStatus", "maneuver_status"),
    ("responsibleNation", "responsible_nation"),
)
_DATETIME_FIELDS = (
    ("createdAt", "udl_created_at"),
    ("eventStartTime", "event_start_time"),
    ("eventStopTime", "event_stop_time"),
)
_FLOAT_FIELDS = (
    ("deltaV", "delta_v"),
    ("thrustMag", "thrust_magnitude"),
    ("thrustDuration", "thrust_duration"),
)

UPDATABLE_COLUMNS: list[str] = [
    *(column for _key, column in _TEXT_FIELDS),
    *(column for _key, column in _DATETIME_FIELDS),
    *(column for _key, column in _FLOAT_FIELDS),
    "sat_no",
    "raw",
]


def _map_udl_record(record: Record) -> Row | None:
    udl_id = record.get("id")
    if not udl_id:
        return None
    mapped: Row = {"udl_id": str(udl_id), "raw": record}
    copy_fields(mapped, record, _TEXT_FIELDS)
    for key, column in _DATETIME_FIELDS:
        set_datetime_if_present(mapped, column, record.get(key))
    for key, column in _FLOAT_FIELDS:
        value = coerce_float(record.get(key))
        if value is not None:
            mapped[column] = value
    set_int_if_present(mapped, "sat_no", record.get("satNo"))
    return mapped


_STORE = RecordStore(
    Maneuver,
    _map_udl_record,
    constraint="uq_maneuver_udl_id",
    updatable=UPDATABLE_COLUMNS,
    audit=("udl.maneuver.ingest", "maneuver_ingest_run"),
)


async def ingest_maneuvers(
    db: AsyncSession,
    client: UDLClient,
    *,
    event_start_time_gte: datetime,
    sat_no: int | None = None,
    data_mode: str | None = None,
    max_results: int | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
) -> IngestResult:
    records = await client.get_maneuvers(
        event_start_time_gte=event_start_time_gte,
        sat_no=sat_no,
        data_mode=data_mode,
        max_results=max_results,
    )
    query = {
        "event_start_time_gte": event_start_time_gte.isoformat(),
        **shared_filters(sat_no, data_mode, max_results),
    }
    return await _STORE.ingest(db, records, query, user_id=user_id, ip_address=ip_address)
