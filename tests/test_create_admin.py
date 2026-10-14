"""The admin CLI (python -m app.cli.create_admin): it creates or resets an admin, records the
change in the audit chain, and takes the password only from the environment or a hidden
prompt, never from the command line."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from app.cli import create_admin
from app.core.security import verify_password
from app.models.user import User, UserRole
from fakes import FakeSession, make_user, scalar_result


def a_password(length: int = 16) -> str:
    return "p" * length


@pytest.fixture
def audit(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    recorder = AsyncMock()
    monkeypatch.setattr(create_admin, "write_audit", recorder)
    return recorder


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> Callable[[User | None], FakeSession]:
    """Point the CLI's session factory at a fake that finds `existing` (or no one)."""

    def install(existing: User | None) -> FakeSession:
        session = FakeSession([scalar_result(existing)])

        @asynccontextmanager
        async def open_session() -> AsyncIterator[FakeSession]:
            yield session

        monkeypatch.setattr(create_admin, "get_session_factory", lambda: open_session)
        return session

    return install


class TestUpsertAdmin:
    async def test_a_new_username_creates_an_active_admin(
        self,
        database: Callable[[User | None], FakeSession],
        audit: AsyncMock,
    ) -> None:
        session = database(None)
        action = await create_admin.upsert_admin(" Alice ", a_password(), "ops@example.org")
        assert action == "created"
        [user] = session.added
        assert user.username == "alice"
        assert user.email == "ops@example.org"
        assert user.role == UserRole.ADMIN.value
        assert user.is_active is True
        assert verify_password(a_password(), user.password_hash)
        written = audit.await_args_list[-1].kwargs
        assert written["action_type"] == "auth.user.admin_upsert"
        assert written["detail"] == {"username": "alice", "action": "created"}
        session.commit.assert_awaited_once()

    async def test_an_existing_user_is_reset_to_an_active_admin(
        self,
        database: Callable[[User | None], FakeSession],
        audit: AsyncMock,
    ) -> None:
        old = a_password(6)
        existing = make_user(password=old, role=UserRole.ANALYST, is_active=False)
        session = database(existing)
        action = await create_admin.upsert_admin("alice", a_password())
        assert action == "updated"
        assert session.added == []
        assert existing.role == UserRole.ADMIN.value
        assert existing.is_active is True
        assert verify_password(a_password(), existing.password_hash)
        assert not verify_password(old, existing.password_hash)
        assert audit.await_args_list[-1].kwargs["entity_id"] == str(existing.id)
        assert audit.await_args_list[-1].kwargs["detail"]["action"] == "updated"


class TestMain:
    @pytest.fixture
    def upsert(self, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
        recorder = AsyncMock(return_value="created")
        monkeypatch.setattr(create_admin, "upsert_admin", recorder)
        return recorder

    def test_the_password_comes_from_the_environment(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        upsert: AsyncMock,
    ) -> None:
        monkeypatch.setenv("ADMIN_PASSWORD", a_password())
        assert create_admin.main(["--username", "Alice", "--email", "ops@example.org"]) == 0
        upsert.assert_awaited_once_with("Alice", a_password(), "ops@example.org")
        assert capsys.readouterr().out == "Admin user 'alice' created.\n"

    def test_otherwise_the_username_and_password_are_prompted_for(
        self,
        monkeypatch: pytest.MonkeyPatch,
        upsert: AsyncMock,
    ) -> None:
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        monkeypatch.delenv("ADMIN_USERNAME", raising=False)
        prompts: list[str] = []

        def answer(prompt: str) -> str:
            prompts.append(prompt)
            return "bob" if prompt.startswith("Username") else a_password()

        monkeypatch.setattr("builtins.input", answer)
        monkeypatch.setattr(create_admin, "getpass", answer)
        assert create_admin.main([]) == 0
        upsert.assert_awaited_once_with("bob", a_password(), None)
        assert prompts == ["Username (admin): ", "Admin password (hidden): "]

    def test_a_password_on_the_command_line_is_refused(self, upsert: AsyncMock) -> None:
        with pytest.raises(SystemExit) as raised:
            create_admin.main(["--username", "alice", "--password", a_password()])
        assert raised.value.code == 2
        upsert.assert_not_awaited()

    @pytest.mark.parametrize(
        ("username", "password", "message"),
        [
            ("alice", "", "A username and a password are both required."),
            ("   ", a_password(), "A username and a password are both required."),
            ("alice", a_password(11), "Use at least 12 characters"),
        ],
    )
    def test_a_missing_or_short_credential_stops_with_status_2(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        upsert: AsyncMock,
        username: str,
        password: str,
        message: str,
    ) -> None:
        monkeypatch.setenv("ADMIN_PASSWORD", password)
        monkeypatch.setattr(create_admin, "getpass", lambda _prompt: "")
        assert create_admin.main(["--username", username]) == 2
        assert message in capsys.readouterr().err
        upsert.assert_not_awaited()
