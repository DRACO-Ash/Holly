"""Element sets (two-line element orbits) pulled from UDL."""

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elset import Elset
from app.services.udl_client import UDLClient
from app.services.udl_records import (
    IngestResult,
    Record,
    RecordStore,
    Row,
    coerce_int,
    parse_datetime,
    shared_filters,
)

logger = logging.getLogger(__name__)

# UDL has used a few different field names across endpoints and sources. Any of these is
# accepted for the identifying columns.
_ID_KEYS = ("id", "idElset", "elsetId")
_SAT_NO_KEYS = ("satNo", "sat_no", "noradCatId", "noradId")
_EPOCH_KEYS = ("epoch", "epochDate", "epochTime")

UDL_TO_MODEL_FIELDS: dict[str, str] = {
    "satNo": "sat_no",
    "epoch": "epoch",
    "meanMotion": "mean_motion",
    "eccentricity": "eccentricity",
    "inclination": "inclination",
    "raan": "raan",
    "argOfPerigee": "arg_of_perigee",
    "meanAnomaly": "mean_anomaly",
    "revNo": "rev_no",
    "bstar": "bstar",
    "meanMotionDot": "mean_motion_dot",
    "meanMotionDDot": "mean_motion_ddot",
    "semiMajorAxis": "semi_major_axis",
    "period": "period",
    "apogee": "apogee",
    "perigee": "perigee",
    "line1": "line1",
    "line2": "line2",
    "classificationMarking": "classification_marking",
    "dataMode": "data_mode",
    "source": "source",
}

UPDATABLE_COLUMNS: list[str] = [*UDL_TO_MODEL_FIELDS.values(), "raw"]


def _first_present(record: Record, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _epoch(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return parse_datetime(value)
        except ValueError:
            logger.warning("Could not parse elset epoch %r; skipping", value)
            return None
    logger.warning("Unexpected elset epoch type %s; skipping", type(value).__name__)
    return None


def _map_udl_record(record: Record) -> Row | None:
    udl_id = _first_present(record, _ID_KEYS)
    sat_no_raw = _first_present(record, _SAT_NO_KEYS)
    epoch_raw = _first_present(record, _EPOCH_KEYS)
    sat_no = coerce_int(sat_no_raw) if sat_no_raw is not None else None
    if not udl_id or sat_no is None or not epoch_raw:
        # Name what was seen, so the field-name sets can be extended if UDL changes again.
        logger.warning(
            "Skipping UDL elset record: id=%r sat_no=%r epoch=%r keys=%s",
            udl_id,
            sat_no_raw,
            epoch_raw,
            sorted(record.keys()),
        )
        return None
    epoch = _epoch(epoch_raw)
    if epoch is None:
        return None

    mapped: Row = {"udl_id": str(udl_id), "sat_no": sat_no, "epoch": epoch, "raw": record}
    for udl_field, model_field in UDL_TO_MODEL_FIELDS.items():
        # satNo and epoch were read above with the tolerant lookup.
        if udl_field not in {"satNo", "epoch"} and udl_field in record:
            mapped[model_field] = record[udl_field]
    return mapped


_STORE = RecordStore(
    Elset,
    _map_udl_record,
    constraint="uq_elset_udl_id",
    updatable=UPDATABLE_COLUMNS,
    audit=("udl.elset.ingest", "elset_ingest_run"),
)


async def ingest_elsets(
    db: AsyncSession,
    client: UDLClient,
    *,
    epoch_gte: datetime,
    sat_no: int | None = None,
    data_mode: str | None = None,
    max_results: int | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
) -> IngestResult:
    records = await client.get_elsets(
        epoch_gte=epoch_gte, sat_no=sat_no, data_mode=data_mode, max_results=max_results
    )
    query = {"epoch_gte": epoch_gte.isoformat(), **shared_filters(sat_no, data_mode, max_results)}
    return await _STORE.ingest(db, records, query, user_id=user_id, ip_address=ip_address)
