"""What every UDL ingest shares: tolerant field mapping, the upsert, and the run result.

Each UDL-sourced table keeps the fields analysts query as typed columns and the whole UDL
payload in `raw` (ADR-007). The mappers are tolerant: a missing, empty or unparseable value
leaves its column out rather than failing the record. A mapped row its table cannot store, such
as text longer than its column or a character PostgreSQL cannot hold, is skipped and counted, so
one bad record does not fail the pull.
"""

import logging
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.storable import UNSTORABLE_TEXT, json_problem, storable_text
from app.services.audit import write_audit

logger = logging.getLogger(__name__)

Record = dict[str, Any]
Row = dict[str, Any]

# PostgreSQL's integer column holds 32 bits.
_INT_RANGE = range(-(2**31), 2**31)

# The UDL envelope fields that several record types carry, as (UDL field, column) pairs.
ENVELOPE_FIELDS = (
    ("dataMode", "data_mode"),
    ("source", "source"),
    ("classificationMarking", "classification_marking"),
    ("createdBy", "created_by"),
    ("origNetwork", "orig_network"),
)


@dataclass(frozen=True)
class IngestResult:
    pulled: int
    inserted: int
    updated: int
    skipped: int


def parse_datetime(value: str) -> datetime:
    # UDL often ends a timestamp with Z (UTC).
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def set_if_present(target: Row, key: str, value: Any) -> None:
    """Set the column unless the value is missing or an empty string."""
    if value is None or value == "":
        return
    target[key] = value


def set_datetime_if_present(target: Row, key: str, value: Any) -> None:
    """Set the column from a datetime or an ISO 8601 string; skip anything unparseable."""
    if isinstance(value, datetime):
        target[key] = value
    elif isinstance(value, str) and value:
        try:
            target[key] = parse_datetime(value)
        except ValueError:
            return


def set_first_present(target: Row, key: str, values: Iterable[Any]) -> None:
    """Set the column from the first usable value, unless it is already set."""
    for value in values:
        if key in target:
            return
        set_if_present(target, key, value)


def copy_fields(target: Row, source: Record, pairs: Iterable[tuple[str, str]]) -> None:
    for source_key, column in pairs:
        set_if_present(target, column, source.get(source_key))


def coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_int_if_present(target: Row, key: str, value: Any) -> None:
    """Set the column from anything int() accepts; skip anything else."""
    number = coerce_int(value)
    if number is not None:
        target[key] = number


def coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def shared_filters(
    sat_no: int | None, data_mode: str | None, max_results: int | None
) -> dict[str, object]:
    """The filters the elset and maneuver pulls share, as their audit entries record them."""
    return {"sat_no": sat_no, "data_mode": data_mode, "max_results": max_results}


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _text_problem(column_type: String, value: Any) -> str | None:
    if not isinstance(value, str):
        return "is not text"
    if not storable_text(value):
        return UNSTORABLE_TEXT
    if column_type.length is not None and len(value) > column_type.length:
        return f"is longer than {column_type.length} characters"
    return None


def _whole_number_problem(column_type: Integer, value: Any) -> str | None:
    if not _is_number(value) or isinstance(value, float):
        return "is not a whole number"
    if not isinstance(column_type, BigInteger) and value not in _INT_RANGE:
        return "is out of range"
    return None


def _unfit(column_type: Any, value: Any) -> str | None:
    """Why `value` cannot be stored in a column of `column_type`, or None when it can."""
    if isinstance(column_type, String):
        return _text_problem(column_type, value)
    if isinstance(column_type, Integer):
        return _whole_number_problem(column_type, value)
    # Float is not a subclass of Numeric in SQLAlchemy 2.1.
    if isinstance(column_type, Float | Numeric):
        return None if _is_number(value) else "is not a number"
    if isinstance(column_type, DateTime) and not isinstance(value, datetime):
        return "is not a time"
    if isinstance(column_type, JSON):
        return json_problem(value)
    return None


def row_problem(model: Any, row: Row) -> str | None:
    """The first value in `row` that its table cannot store, naming the column but never the
    value; None when the whole row fits."""
    columns = model.__table__.columns
    # Typed columns first, so a problem is named by the column analysts know; then the JSON
    # columns, such as raw, which repeats every field of the record.
    for key, value in sorted(row.items(), key=lambda item: isinstance(columns[item[0]].type, JSON)):
        if value is not None and (reason := _unfit(columns[key].type, value)):
            return f"{key} {reason}"
    return None


def map_records(
    records: Sequence[Record], mapper: Callable[[Record], Row | None], model: Any
) -> tuple[list[Row], int]:
    """The mapped rows, one per UDL id (the latest wins), and how many records were skipped:
    those the mapper refused, those the table cannot store, and repeats of an id already in
    the same pull."""
    by_udl_id: dict[str, Row] = {}
    for record in records:
        row = mapper(record)
        if row is None:
            continue
        problem = row_problem(model, row)
        if problem is not None:
            logger.warning("Skipping UDL record %.64s: %s", row["udl_id"], problem)
            continue
        by_udl_id[row["udl_id"]] = row
    return list(by_udl_id.values()), len(records) - len(by_udl_id)


async def upsert_rows(
    db: AsyncSession,
    model: Any,
    rows: list[Row],
    *,
    constraint: str,
    updatable: Sequence[str],
) -> tuple[int, int]:
    """Insert new rows and update existing ones, keyed on udl_id. Returns (inserted, updated)."""
    if not rows:
        return 0, 0
    # A multi-row VALUES clause needs the same columns in every row, but UDL records vary in
    # shape, so missing columns are filled with None.
    columns = set().union(*(row.keys() for row in rows))
    for row in rows:
        for column in columns:
            row.setdefault(column, None)

    udl_ids = [row["udl_id"] for row in rows]
    existing = await db.execute(select(model.udl_id).where(model.udl_id.in_(udl_ids)))
    existing_ids = {udl_id for (udl_id,) in existing.all()}

    stmt = pg_insert(model).values(rows)
    update_columns: dict[str, Any] = {
        column: getattr(stmt.excluded, column) for column in updatable
    }
    update_columns["updated_at"] = func.now()
    await db.execute(stmt.on_conflict_do_update(constraint=constraint, set_=update_columns))

    inserted = sum(1 for udl_id in udl_ids if udl_id not in existing_ids)
    return inserted, len(rows) - inserted


async def ingest_records(
    db: AsyncSession,
    records: Sequence[Record],
    mapper: Callable[[Record], Row | None],
    model: Any,
    *,
    constraint: str,
    updatable: Sequence[str],
) -> IngestResult:
    """Map and upsert one UDL pull. The caller audits and commits."""
    rows, skipped = map_records(records, mapper, model)
    inserted, updated = await upsert_rows(
        db, model, rows, constraint=constraint, updatable=updatable
    )
    return IngestResult(pulled=len(records), inserted=inserted, updated=updated, skipped=skipped)


@dataclass(frozen=True)
class RecordStore:
    """Where one kind of UDL record is kept: its model, how a record becomes a row, the unique
    constraint an upsert meets on, the columns a newer publication may change, and the audit
    action and entity type each pull is recorded under."""

    model: Any
    mapper: Callable[[Record], Row | None]
    constraint: str
    updatable: Sequence[str]
    audit: tuple[str, str]

    async def ingest(
        self,
        db: AsyncSession,
        records: Sequence[Record],
        query: Mapping[str, object],
        *,
        user_id: uuid.UUID | None,
        ip_address: str | None,
    ) -> IngestResult:
        """Map and upsert one UDL pull, audit it with the query that drove it, and commit."""
        result = await ingest_records(
            db,
            records,
            self.mapper,
            self.model,
            constraint=self.constraint,
            updatable=self.updatable,
        )
        action_type, entity_type = self.audit
        await write_audit(
            db,
            action_type=action_type,
            entity_type=entity_type,
            user_id=user_id,
            ip_address=ip_address,
            detail={**query, **asdict(result)},
        )
        await db.commit()
        return result
