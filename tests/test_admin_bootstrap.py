"""The first admin from the environment (app/admin_bootstrap.py): created once, under a lock, only
while no account exists, and a half-set or weak pair stops the start without naming its value."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import admin_bootstrap
from app.core.security import verify_password
from app.db import session as db_session
from app.models.user import UserRole
from app.services.audit import AUDIT_ADVISORY_LOCK_KEY
from fakes import FakeSession, scalar_result

PASSWORD = "p" * 16
MIGRATIONS_ENV = Path(admin_bootstrap.__file__).parent / "migrations" / "env.py"


@pytest.fixture
def audit(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    recorder = AsyncMock()
    monkeypatch.setattr(admin_bootstrap, "write_audit", recorder)
    return recorder


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> Callable[[int], FakeSession]:
    """Point the bootstrap at a fake that counts `accounts` after taking its lock."""

    def install(accounts: int) -> FakeSession:
        session = FakeSession([MagicMock(), scalar_result(accounts)])

        @asynccontextmanager
        async def open_session() -> AsyncIterator[FakeSession]:
            yield session

        monkeypatch.setattr(admin_bootstrap, "get_session_factory", lambda: open_session)
        return session

    return install


def logged(captured: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in captured.splitlines() if line.startswith("{")]


async def test_no_account_and_both_variables_create_one_active_admin(
    database: Callable[[int], FakeSession],
    audit: AsyncMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = database(0)
    env = {
        "ADMIN_USERNAME": " Alice ",
        "ADMIN_PASSWORD": PASSWORD,
        "ADMIN_EMAIL": " ops@example.org ",
    }
    assert await admin_bootstrap.bootstrap_admin(env) == "created"
    lock = session.execute.await_args_list[0].args
    assert "pg_advisory_xact_lock" in str(lock[0])
    assert lock[1] == {"key": admin_bootstrap.ADMIN_BOOTSTRAP_LOCK_KEY}
    [user] = session.added
    assert user.username == "alice"
    assert user.email == "ops@example.org"
    assert user.role == UserRole.ADMIN.value
    assert user.is_active is True
    assert verify_password(PASSWORD, user.password_hash)
    assert audit.await_args is not None
    written = audit.await_args.kwargs
    assert written["action_type"] == "auth.user.admin_bootstrap"
    assert written["detail"] == {"username": "alice"}
    session.commit.assert_awaited_once()
    captured = capsys.readouterr().out
    assert PASSWORD not in captured
    assert logged(captured)[-1]["status"] == "created"


@pytest.mark.parametrize(
    ("env", "still_set"),
    [
        (
            {"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": PASSWORD},
            ["ADMIN_USERNAME", "ADMIN_PASSWORD"],
        ),
        # The password removed after the first start, as the operator manual says to.
        (
            {"ADMIN_USERNAME": "alice", "ADMIN_EMAIL": "ops@example.org"},
            ["ADMIN_USERNAME", "ADMIN_EMAIL"],
        ),
        # Values no first start would accept are never read once an account exists.
        ({"ADMIN_PASSWORD": "short", "ADMIN_EMAIL": "e" * 300}, ["ADMIN_PASSWORD", "ADMIN_EMAIL"]),
    ],
)
async def test_an_existing_account_leaves_everything_alone_whatever_is_still_set(
    database: Callable[[int], FakeSession],
    audit: AsyncMock,
    capsys: pytest.CaptureFixture[str],
    env: dict[str, str],
    still_set: list[str],
) -> None:
    session = database(1)
    assert await admin_bootstrap.bootstrap_admin(env) == "accounts_exist"
    assert session.added == []
    audit.assert_not_awaited()
    session.commit.assert_awaited_once()
    captured = capsys.readouterr().out
    line = logged(captured)[-1]
    assert line["status"] == "accounts_exist"
    assert line["variables_still_set"] == still_set
    for value in env.values():
        assert value not in captured


async def test_neither_variable_set_touches_no_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    opened = MagicMock()
    monkeypatch.setattr(admin_bootstrap, "get_session_factory", opened)
    assert await admin_bootstrap.bootstrap_admin({"ADMIN_EMAIL": "ops@example.org"}) == (
        "not_configured"
    )
    # Spaces alone set nothing.
    assert await admin_bootstrap.bootstrap_admin({"ADMIN_USERNAME": "   "}) == "not_configured"
    opened.assert_not_called()
    lines = logged(capsys.readouterr().out)
    assert [line["status"] for line in lines] == ["not_configured", "not_configured"]
    # The log names what is still set, never its value.
    assert [line["variables_still_set"] for line in lines] == [["ADMIN_EMAIL"], []]


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"ADMIN_USERNAME": "alice"}, "ADMIN_PASSWORD is not set"),
        ({"ADMIN_USERNAME": "  ", "ADMIN_PASSWORD": PASSWORD}, "ADMIN_USERNAME is not set"),
        ({"ADMIN_PASSWORD": PASSWORD}, "ADMIN_USERNAME is not set"),
        ({"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": "p" * 11}, "at least 12 characters"),
        ({"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": " " * 12}, "ADMIN_PASSWORD is not set"),
        ({"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": "p" * 12 + "\udcff"}, "not valid UTF-8"),
        ({"ADMIN_USERNAME": "a" * 51, "ADMIN_PASSWORD": PASSWORD}, "1 to 50 printable"),
        ({"ADMIN_USERNAME": "al\x00ice", "ADMIN_PASSWORD": PASSWORD}, "1 to 50 printable"),
        ({"ADMIN_USERNAME": "al\u202eice", "ADMIN_PASSWORD": PASSWORD}, "1 to 50 printable"),
        ({"ADMIN_USERNAME": "al\ud800ice", "ADMIN_PASSWORD": PASSWORD}, "1 to 50 printable"),
        (
            {"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": PASSWORD, "ADMIN_EMAIL": "e" * 256},
            "ADMIN_EMAIL must be at most 255",
        ),
        (
            {"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": PASSWORD, "ADMIN_EMAIL": "e\udcffx"},
            "ADMIN_EMAIL must be at most 255",
        ),
        (
            {"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": PASSWORD, "ADMIN_EMAIL": "e\x00x"},
            "ADMIN_EMAIL must be at most 255",
        ),
        (
            {
                "ADMIN_USERNAME": "alice",
                "ADMIN_PASSWORD": PASSWORD,
                "ADMIN_EMAIL": "ops\u202e@x.org",
            },
            "ADMIN_EMAIL must be at most 255",
        ),
        (
            {"ADMIN_USERNAME": "alice", "ADMIN_PASSWORD": PASSWORD, "ADMIN_EMAIL": "ops\x1b@x.org"},
            "ADMIN_EMAIL must be at most 255",
        ),
    ],
)
async def test_with_no_account_a_half_set_or_weak_pair_stops_the_start_without_its_value(
    database: Callable[[int], FakeSession],
    audit: AsyncMock,
    env: dict[str, str],
    message: str,
) -> None:
    session = database(0)
    with pytest.raises(RuntimeError, match=message) as raised:
        await admin_bootstrap.bootstrap_admin(env)
    # The message names the variable and holds none of the value.
    for value in filter(str.strip, env.values()):
        assert value.strip() not in str(raised.value)
    assert "\udcff" not in str(raised.value)
    # Only the lock and the count ran: no value reached a query, and nothing was written.
    assert session.execute.await_count == 2
    assert session.added == []
    audit.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_the_master_releases_its_connections_before_the_worker_forks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def refuse(_env: dict[str, str]) -> str:
        calls.append("bootstrap")
        raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters")

    monkeypatch.setattr(admin_bootstrap, "bootstrap_admin", AsyncMock(side_effect=refuse))
    monkeypatch.setattr(
        admin_bootstrap, "dispose_engine", AsyncMock(side_effect=lambda: calls.append("dispose"))
    )
    with pytest.raises(RuntimeError, match="at least 12"):
        admin_bootstrap.run_admin_bootstrap({})
    assert calls == ["bootstrap", "dispose"]


def test_the_engine_never_logs_a_statement_s_values() -> None:
    # A refused insert would otherwise print its bound values, a password hash among them.
    db_session.get_engine.cache_clear()
    try:
        assert db_session.get_engine().sync_engine.hide_parameters is True
    finally:
        db_session.get_engine.cache_clear()


def test_the_bootstrap_lock_is_not_the_migrations_or_the_audit_chain_s() -> None:
    # Sharing a key would make one wait on the other for no reason.
    keys = {
        admin_bootstrap.ADMIN_BOOTSTRAP_LOCK_KEY,
        AUDIT_ADVISORY_LOCK_KEY,
        int(
            MIGRATIONS_ENV.read_text(encoding="utf-8")
            .split("MIGRATION_ADVISORY_LOCK_KEY = ")[1]
            .split()[0],
            16,
        ),
    }
    assert len(keys) == 3


@pytest.mark.usefixtures("audit")
async def test_the_longest_username_and_email_holly_stores_are_accepted(
    database: Callable[[int], FakeSession],
) -> None:
    session = database(0)
    env = {"ADMIN_USERNAME": "\u00e9" * 50, "ADMIN_PASSWORD": PASSWORD, "ADMIN_EMAIL": "e" * 255}
    assert await admin_bootstrap.bootstrap_admin(env) == "created"
    [user] = session.added
    assert (len(user.username), len(user.email)) == (50, 255)
