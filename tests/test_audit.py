"""The tamper-evident audit chain (ADR-008): what write_audit stores, that every stored row
can be recomputed from its own fields, that the verifier finds the first broken link, and
that only operators and admins can read the log."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from app.cli import verify_audit
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.services.audit import expected_entry_hash, first_broken_link, write_audit
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]


def _latest(previous: tuple[str, datetime] | None) -> MagicMock:
    """The writer's read of the newest row: its hash and timestamp, or no row at all."""
    result = MagicMock()
    result.one_or_none.return_value = previous
    return result


async def _write(previous: tuple[str, datetime] | None, **fields: Any) -> AuditLog:
    session = FakeSession([None, _latest(previous)])
    entry = await write_audit(session, **fields)  # type: ignore[arg-type]
    assert session.added == [entry]
    session.flush.assert_awaited_once()
    return entry


async def _chain(length: int) -> list[AuditLog]:
    rows: list[AuditLog] = []
    for number in range(length):
        previous = (rows[-1].entry_hash, rows[-1].timestamp) if rows else None
        rows.append(await _write(previous, action_type="test.event", detail={"number": number}))
    return rows


class TestWriteAudit:
    async def test_the_first_entry_has_no_previous_hash_and_verifies(self) -> None:
        user_id = uuid.uuid4()
        entry = await _write(
            None,
            action_type="auth.user.login",
            entity_type="user",
            entity_id=str(user_id),
            user_id=user_id,
            ip_address="10.0.0.1",
            detail={"success": True},
        )
        assert entry.previous_hash is None
        assert entry.action_type == "auth.user.login"
        assert entry.user_id == user_id
        assert json.loads(entry.detail or "") == {"success": True}
        assert entry.timestamp.tzinfo is not None
        assert len(entry.entry_hash) == 64
        assert entry.entry_hash == expected_entry_hash(entry)

    async def test_an_entry_links_to_the_latest_hash(self) -> None:
        entry = await _write(("a" * 64, NOW), action_type="test.event")
        assert entry.previous_hash == "a" * 64
        assert entry.entry_hash == expected_entry_hash(entry)

    async def test_an_entry_is_timed_after_the_latest_even_when_this_clock_is_behind(
        self,
    ) -> None:
        # Another container, its clock an hour ahead, wrote the latest row.
        ahead = datetime.now(UTC) + timedelta(hours=1)
        entry = await _write(("a" * 64, ahead), action_type="test.event")
        assert entry.timestamp == ahead + timedelta(microseconds=1)
        assert entry.entry_hash == expected_entry_hash(entry)

    async def test_a_clock_ahead_of_the_chain_keeps_its_own_time(self) -> None:
        before = datetime.now(UTC)
        entry = await _write(("a" * 64, NOW - timedelta(days=1)), action_type="test.event")
        assert before <= entry.timestamp <= datetime.now(UTC)

    async def test_the_writer_takes_the_chain_lock_first(self) -> None:
        session = FakeSession([None, _latest(None)])
        await write_audit(session, action_type="test.event")  # type: ignore[arg-type]
        lock_statement = session.execute.await_args_list[0].args[0]
        assert "pg_advisory_xact_lock" in str(lock_statement)

    async def test_values_json_cannot_hold_are_stored_as_text_and_still_verify(self) -> None:
        detail = {"when": datetime(2026, 1, 2, tzinfo=UTC), "id": uuid.UUID(int=7)}
        entry = await _write(None, action_type="test.event", detail=detail)
        assert json.loads(entry.detail or "") == {
            "when": "2026-01-02 00:00:00+00:00",
            "id": "00000000-0000-0000-0000-000000000007",
        }
        assert entry.entry_hash == expected_entry_hash(entry)

    async def test_an_entry_without_detail_stores_none(self) -> None:
        entry = await _write(None, action_type="test.event")
        assert entry.detail is None
        assert entry.entry_hash == expected_entry_hash(entry)


class TestTheVerifier:
    async def test_an_intact_chain_verifies(self) -> None:
        assert first_broken_link(await _chain(3)) is None

    def test_an_empty_chain_verifies(self) -> None:
        assert first_broken_link([]) is None

    @pytest.mark.parametrize(
        "tamper",
        [
            lambda row: setattr(row, "detail", json.dumps({"number": 99})),
            lambda row: setattr(row, "action_type", "test.other"),
            lambda row: setattr(row, "timestamp", row.timestamp + timedelta(seconds=1)),
            lambda row: setattr(row, "ip_address", "10.9.9.9"),
            lambda row: setattr(row, "previous_hash", "b" * 64),
        ],
    )
    async def test_an_edited_row_is_found(self, tamper: Callable[[AuditLog], None]) -> None:
        rows = await _chain(3)
        tamper(rows[1])
        assert first_broken_link(rows) == 1

    async def test_a_deleted_row_breaks_the_link_after_it(self) -> None:
        rows = await _chain(3)
        assert first_broken_link([rows[0], rows[2]]) == 1

    async def test_the_report_names_the_first_broken_row(self) -> None:
        rows = await _chain(2)
        rows[1].action_type = "test.other"
        status, message = verify_audit.report(rows)
        assert status == 1
        assert message.startswith("Audit chain broken at entry 2 of 2: ")
        assert str(rows[1].id) in message

    async def test_the_report_counts_an_intact_chain(self) -> None:
        assert verify_audit.report(await _chain(2)) == (
            0,
            "Audit chain intact: 2 entries verified.",
        )

    @pytest.mark.parametrize(("break_it", "status"), [(False, 0), (True, 1)])
    async def test_main_exits_with_the_report_status(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        break_it: bool,
        status: int,
    ) -> None:
        rows = await _chain(2)
        if break_it:
            rows[0].detail = None
        session = FakeSession([rows_result(rows)])

        @asynccontextmanager
        async def open_session() -> AsyncIterator[FakeSession]:
            yield session

        monkeypatch.setattr(verify_audit, "get_session_factory", lambda: open_session)
        # main() runs its own event loop, so it is called from a worker thread here.
        assert await asyncio.to_thread(verify_audit.main) == status
        captured = capsys.readouterr()
        assert ("Audit chain intact" in captured.out) is (status == 0)
        assert ("Audit chain broken" in captured.err) is (status == 1)


def _audit_row(action_type: str = "udl.elset.ingest") -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        timestamp=NOW,
        user_id=uuid.uuid4(),
        action_type=action_type,
        entity_type="elset_ingest_run",
        entity_id=None,
        ip_address="127.0.0.1",
        detail='{"success": true}',
        previous_hash=None,
        entry_hash="a" * 64,
    )


class TestTheAuditRoute:
    async def test_it_requires_sign_in(self, api: httpx2.AsyncClient) -> None:
        assert (await api.get("/api/v1/audit")).status_code == 401

    async def test_an_analyst_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn
    ) -> None:
        sign_in(make_user(role=UserRole.ANALYST))
        use_session(FakeSession())
        response = await api.get("/api/v1/audit")
        assert response.status_code == 403

    @pytest.mark.parametrize("role", [UserRole.OPERATOR, UserRole.ADMIN])
    async def test_operators_and_admins_read_a_page(
        self, api: httpx2.AsyncClient, use_session: UseSession, sign_in: SignIn, role: UserRole
    ) -> None:
        sign_in(make_user(role=role))
        rows = [_audit_row(), _audit_row("auth.user.login")]
        use_session(FakeSession([scalar_result(42), rows_result(rows)]))
        response = await api.get(
            "/api/v1/audit",
            params={
                "action_type": "udl.elset.ingest",
                "user_id": str(uuid.uuid4()),
                "since": "2026-06-01T00:00:00Z",
                "until": "2026-06-30T00:00:00Z",
                "limit": 20,
                "offset": 40,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 42
        assert (body["limit"], body["offset"]) == (20, 40)
        assert [item["action_type"] for item in body["items"]] == [
            "udl.elset.ingest",
            "auth.user.login",
        ]
        assert body["items"][0]["entry_hash"] == "a" * 64

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}])
    async def test_paging_outside_its_bounds_is_422(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        params: dict[str, int],
    ) -> None:
        sign_in(make_user(role=UserRole.ADMIN))
        use_session(FakeSession())
        assert (await api.get("/api/v1/audit", params=params)).status_code == 422
