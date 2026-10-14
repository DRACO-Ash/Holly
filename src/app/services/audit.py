"""The tamper-evident audit chain (ADR-008).

Each row's entry_hash is the SHA-256 of the previous entry_hash followed by the canonical JSON
payload. The payload holds the row's own fields, including its timestamp, so anyone can
recompute every hash from the table alone (expected_entry_hash, first_broken_link). A
PostgreSQL advisory lock taken inside the transaction serialises writers, and the timestamp is
read after the lock, so the chain's timestamp order is its write order.
"""

import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

AUDIT_ADVISORY_LOCK_KEY = 0x4F505841


def _serialise_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _compute_entry_hash(previous_hash: str | None, serialised_payload: str) -> str:
    chain_input = (previous_hash or "") + serialised_payload
    return hashlib.sha256(chain_input.encode("utf-8")).hexdigest()


def _payload(
    *,
    action_type: str,
    entity_type: str | None,
    entity_id: str | None,
    user_id: uuid.UUID | None,
    ip_address: str | None,
    detail: Any,
    timestamp: datetime,
) -> dict[str, Any]:
    return {
        "action_type": action_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "user_id": str(user_id) if user_id is not None else None,
        "ip_address": ip_address,
        "detail": detail,
        "timestamp": timestamp.isoformat(),
    }


async def write_audit(
    db: AsyncSession,
    *,
    action_type: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:k)"),
        {"k": AUDIT_ADVISORY_LOCK_KEY},
    )
    latest = await db.execute(
        select(AuditLog.entry_hash).order_by(AuditLog.timestamp.desc()).limit(1)
    )
    previous_hash = latest.scalar_one_or_none()

    # Stored detail goes through the same str() fallback as the hash, so json.loads of the
    # stored text reproduces exactly what was hashed.
    stored_detail = json.dumps(detail, default=str) if detail is not None else None
    timestamp = datetime.now(UTC)
    payload = _payload(
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        ip_address=ip_address,
        detail=json.loads(stored_detail) if stored_detail is not None else None,
        timestamp=timestamp,
    )
    entry = AuditLog(
        timestamp=timestamp,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        ip_address=ip_address,
        detail=stored_detail,
        previous_hash=previous_hash,
        entry_hash=_compute_entry_hash(previous_hash, _serialise_payload(payload)),
    )
    db.add(entry)
    await db.flush()
    return entry


def expected_entry_hash(row: AuditLog) -> str:
    """The entry_hash this row should carry, recomputed from its own fields."""
    payload = _payload(
        action_type=row.action_type,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        user_id=row.user_id,
        ip_address=row.ip_address,
        detail=json.loads(row.detail) if row.detail is not None else None,
        timestamp=row.timestamp,
    )
    return _compute_entry_hash(row.previous_hash, _serialise_payload(payload))


def first_broken_link(rows: Sequence[AuditLog]) -> int | None:
    """The index of the first row, in timestamp order, that does not verify; None when the
    whole chain verifies. A row fails when it does not point at the previous row's hash, or
    when its own hash does not match its fields."""
    previous: str | None = None
    for index, row in enumerate(rows):
        if row.previous_hash != previous or row.entry_hash != expected_entry_hash(row):
            return index
        previous = row.entry_hash
    return None
