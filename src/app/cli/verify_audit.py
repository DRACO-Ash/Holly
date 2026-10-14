"""Verify the audit chain: python -m app.cli.verify_audit

Walks audit.audit_log in timestamp order, recomputes every entry_hash from the row's own
fields (app/services/audit.py), and reports the first row that does not verify. The exit
status is 0 when the whole chain verifies and 1 when it does not.

Rows written by the Daily Operations Dashboard, before Holly V0.2, hashed a timestamp that was
never stored, so they cannot be recomputed; a chain that starts with such rows reports its
first row as the break.
"""

import asyncio
import sys
from collections.abc import Sequence

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.audit import AuditLog
from app.services.audit import first_broken_link


async def load_chain() -> Sequence[AuditLog]:
    async with get_session_factory()() as db:
        stmt = select(AuditLog).order_by(AuditLog.timestamp.asc())
        return (await db.execute(stmt)).scalars().all()


def report(rows: Sequence[AuditLog]) -> tuple[int, str]:
    """(exit status, message) for a chain in timestamp order."""
    index = first_broken_link(rows)
    if index is None:
        return 0, f"Audit chain intact: {len(rows)} entries verified."
    row = rows[index]
    return 1, (
        f"Audit chain broken at entry {index + 1} of {len(rows)}: id {row.id}, "
        f"{row.timestamp.isoformat()}, {row.action_type}."
    )


def main() -> int:
    status, message = report(asyncio.run(load_chain()))
    (sys.stdout if status == 0 else sys.stderr).write(message + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
