"""The Users page's routes (app/api/v1/routes/users.py): admins only; a new or reset password is
temporary and ends every earlier session; no admin can change their own account here, and the
last active admin stays one."""

import uuid
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.api.v1.routes import users
from app.core.rate_limit import LOGIN_LIMIT
from app.core.security import verify_password
from app.models.user import User, UserRole
from fakes import NOW, FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]
SignIn = Callable[[User], User]

USERS = "/api/v1/users"
POSTGRESQL = postgresql.dialect()  # type: ignore[no-untyped-call]
# A temporary password of the length Holly requires; test-only.
TEMPORARY = "a-temporary-password"


@pytest.fixture
def audit_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def record(_db: object, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(users, "write_audit", AsyncMock(side_effect=record))
    return calls


@pytest.fixture
def admin(sign_in: SignIn) -> User:
    return sign_in(make_user(username="root", role=UserRole.ADMIN))


def stored(session: FakeSession) -> FakeSession:
    """Make the fake's flush and refresh fill in what the database would: an id and a time."""

    def flush() -> None:
        for row in session.added:
            row.id = row.id or uuid.uuid4()

    def refresh(row: User) -> None:
        row.created_at = row.created_at or NOW

    session.flush.side_effect = flush
    session.refresh.side_effect = refresh
    return session


def sql(session: FakeSession, call: int) -> str:
    statement = session.execute.await_args_list[call].args[0]
    return str(statement.compile(dialect=POSTGRESQL))


def assert_locked_afresh(session: FakeSession, call: int) -> None:
    """The rows were read again, in id order, under a lock a foreign-key check does not wait
    for (services/accounts.py), so no change committed since the request began is undone."""
    statement = session.execute.await_args_list[call].args[0]
    assert statement.get_execution_options()["populate_existing"] is True
    assert sql(session, call).endswith("ORDER BY app_user.id FOR NO KEY UPDATE")


class TestOnlyAdmins:
    @pytest.mark.parametrize("role", [UserRole.ANALYST, UserRole.OPERATOR])
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", USERS),
            ("POST", USERS),
            ("POST", f"{USERS}/{uuid.uuid4()}/password"),
            ("PATCH", f"{USERS}/{uuid.uuid4()}"),
        ],
    )
    async def test_anyone_else_is_refused_before_any_query(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        sign_in: SignIn,
        role: UserRole,
        method: str,
        path: str,
    ) -> None:
        sign_in(make_user(role=role))
        session = use_session(FakeSession())
        response = await api.request(method, path, json={})
        assert response.status_code == 403
        session.execute.assert_not_awaited()


@pytest.mark.usefixtures("admin")
class TestList:
    async def test_every_account_is_listed_by_username_without_its_hash(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        bob = make_user(username="bob", must_change_password=True)
        session = use_session(FakeSession([rows_result([bob])]))
        response = await api.get(USERS)
        assert response.status_code == 200
        [row] = response.json()
        assert row["username"] == "bob"
        assert row["must_change_password"] is True
        assert "password_hash" not in row
        assert "token_version" not in row
        assert "ORDER BY app_user.username" in sql(session, 0)


class TestCreate:
    async def test_a_new_account_must_choose_its_own_password(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        admin: User,
        audit_calls: list[dict[str, Any]],
    ) -> None:
        session = use_session(stored(FakeSession([scalar_result(None)])))
        body = {
            "username": " Bob ",
            "email": "bob@example.org",
            "role": "operator",
            "temporary_password": TEMPORARY,
        }
        response = await api.post(USERS, json=body)
        assert response.status_code == 201
        [user] = session.added
        assert (user.username, user.email, user.role) == ("bob", "bob@example.org", "operator")
        assert user.must_change_password is True
        assert user.is_active is True
        assert user.token_version == 0
        assert verify_password(TEMPORARY, user.password_hash)
        assert response.json()["username"] == "bob"
        assert response.json()["must_change_password"] is True
        assert TEMPORARY not in response.text
        [call] = audit_calls
        assert call["action_type"] == "auth.user.create"
        assert call["user_id"] == admin.id
        assert call["entity_id"] == str(user.id)
        assert call["detail"] == {"username": "bob", "role": "operator"}
        # The name and the email are both checked before the insert, the email in any case.
        assert "app_user.username = " in sql(session, 0)
        assert "lower(app_user.email) = " in sql(session, 0)
        session.commit.assert_awaited_once()

    async def test_an_empty_email_means_none_and_the_role_defaults_to_analyst(
        self, api: httpx2.AsyncClient, use_session: UseSession, admin: User
    ) -> None:
        assert admin.role == UserRole.ADMIN.value
        session = use_session(stored(FakeSession([scalar_result(None)])))
        users.write_audit = AsyncMock()  # type: ignore[attr-defined]
        response = await api.post(
            USERS, json={"username": "carol", "email": "  ", "temporary_password": TEMPORARY}
        )
        assert response.status_code == 201
        [user] = session.added
        assert user.email is None
        assert user.role == "analyst"
        assert "app_user.email" not in sql(session, 0)

    @pytest.mark.usefixtures("admin", "audit_calls")
    async def test_a_name_of_letters_digits_and_the_four_marks_is_taken(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        session = use_session(stored(FakeSession([scalar_result(None)])))
        body = {"username": "J.Smith_2-ops@ukwatch", "temporary_password": TEMPORARY}
        response = await api.post(USERS, json=body)
        assert response.status_code == 201
        assert session.added[0].username == "j.smith_2-ops@ukwatch"

    @pytest.mark.usefixtures("admin", "audit_calls")
    async def test_a_name_or_email_in_use_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        session = use_session(FakeSession([scalar_result(uuid.uuid4())]))
        response = await api.post(
            USERS, json={"username": "alice", "temporary_password": TEMPORARY}
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "That username or email is already in use."}
        assert session.added == []

    async def test_a_name_taken_between_the_check_and_the_insert_is_refused(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        admin: User,
        audit_calls: list[dict[str, Any]],
    ) -> None:
        assert admin.is_active
        session = use_session(FakeSession([scalar_result(None)]))
        session.flush.side_effect = IntegrityError("INSERT", {}, Exception("unique"))
        response = await api.post(
            USERS, json={"username": "alice", "temporary_password": TEMPORARY}
        )
        assert response.status_code == 409
        session.rollback.assert_awaited_once()
        session.commit.assert_not_awaited()
        assert audit_calls == []

    @pytest.mark.usefixtures("admin")
    @pytest.mark.parametrize(
        "body",
        [
            {"username": "", "temporary_password": TEMPORARY},
            {"username": "a" * 51, "temporary_password": TEMPORARY},
            {"username": "al\u202eice", "temporary_password": TEMPORARY},
            # Look-alikes: a Cyrillic a, a combining accent, a space.
            {"username": "\u0430dmin", "temporary_password": TEMPORARY},
            {"username": "admin\u0301", "temporary_password": TEMPORARY},
            {"username": "bob smith", "temporary_password": TEMPORARY},
            {"username": "alice", "temporary_password": "p" * 11},
            {"username": "alice", "temporary_password": " " * 12},
            {"username": "alice", "email": "e" * 256, "temporary_password": TEMPORARY},
            {"username": "alice", "role": "root", "temporary_password": TEMPORARY},
            {"username": "alice"},
            ["not", "an", "object"],
        ],
    )
    async def test_a_value_holly_would_not_store_is_refused_before_any_query(
        self, api: httpx2.AsyncClient, use_session: UseSession, body: object
    ) -> None:
        session = use_session(FakeSession())
        response = await api.post(USERS, json=body)
        assert response.status_code == 422
        session.execute.assert_not_awaited()


class TestResetPassword:
    async def test_a_reset_is_temporary_ends_every_session_and_lifts_a_lockout(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        admin: User,
        audit_calls: list[dict[str, Any]],
    ) -> None:
        bob = make_user(username="bob", token_version=2)
        session = use_session(stored(FakeSession([rows_result([bob])])))
        for _ in range(10):
            LOGIN_LIMIT.record("bob")
        response = await api.post(
            f"{USERS}/{bob.id}/password", json={"temporary_password": TEMPORARY}
        )
        assert response.status_code == 200
        assert verify_password(TEMPORARY, bob.password_hash)
        assert bob.must_change_password is True
        assert bob.token_version == 3
        assert_locked_afresh(session, 0)
        assert LOGIN_LIMIT.wait_time("bob") == 0
        [call] = audit_calls
        assert call["action_type"] == "auth.user.password_reset"
        assert call["user_id"] == admin.id
        assert call["detail"] == {"username": "bob"}
        assert TEMPORARY not in str(call)
        session.commit.assert_awaited_once()

    async def test_an_admin_cannot_reset_their_own_password_here(
        self, api: httpx2.AsyncClient, use_session: UseSession, admin: User
    ) -> None:
        session = use_session(FakeSession())
        response = await api.post(
            f"{USERS}/{admin.id}/password", json={"temporary_password": TEMPORARY}
        )
        assert response.status_code == 409
        session.execute.assert_not_awaited()

    @pytest.mark.usefixtures("admin")
    async def test_an_unknown_account_is_404(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        use_session(FakeSession([rows_result([])]))
        response = await api.post(
            f"{USERS}/{uuid.uuid4()}/password", json={"temporary_password": TEMPORARY}
        )
        assert response.status_code == 404

    @pytest.mark.usefixtures("admin")
    async def test_an_unknown_account_is_404_on_a_change_too(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        # Only the active admins came back: the account named is not among them.
        use_session(FakeSession([rows_result([make_user(role=UserRole.ADMIN)])]))
        response = await api.patch(f"{USERS}/{uuid.uuid4()}", json={"is_active": False})
        assert response.status_code == 404


class TestUpdate:
    async def test_deactivating_ends_every_session_for_good(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        admin: User,
        audit_calls: list[dict[str, Any]],
    ) -> None:
        bob = make_user(username="bob", token_version=1)
        use_session(stored(FakeSession([rows_result([bob])])))
        response = await api.patch(f"{USERS}/{bob.id}", json={"is_active": False})
        assert response.status_code == 200
        assert bob.is_active is False
        assert bob.token_version == 2
        [call] = audit_calls
        assert call["action_type"] == "auth.user.update"
        assert call["user_id"] == admin.id
        assert call["detail"] == {"username": "bob", "is_active": {"from": True, "to": False}}

    @pytest.mark.usefixtures("admin")
    async def test_activating_again_brings_no_old_session_back(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        bob = make_user(username="bob", is_active=False, token_version=2)
        use_session(stored(FakeSession([rows_result([bob])])))
        response = await api.patch(f"{USERS}/{bob.id}", json={"is_active": True})
        assert response.status_code == 200
        assert bob.is_active is True
        assert bob.token_version == 2
        assert audit_calls[0]["detail"]["is_active"] == {"from": False, "to": True}

    @pytest.mark.usefixtures("admin")
    async def test_a_role_change_is_audited_from_and_to(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        bob = make_user(username="bob")
        use_session(stored(FakeSession([rows_result([bob])])))
        response = await api.patch(f"{USERS}/{bob.id}", json={"role": "operator"})
        assert response.status_code == 200
        assert bob.role == "operator"
        assert bob.token_version == 0
        assert audit_calls[0]["detail"] == {
            "username": "bob",
            "role": {"from": "analyst", "to": "operator"},
        }

    @pytest.mark.usefixtures("admin")
    async def test_a_change_to_what_is_already_set_writes_nothing(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        bob = make_user(username="bob")
        session = use_session(FakeSession([rows_result([bob])]))
        response = await api.patch(f"{USERS}/{bob.id}", json={"role": "analyst", "is_active": True})
        assert response.status_code == 200
        assert audit_calls == []
        session.commit.assert_not_awaited()

    @pytest.mark.usefixtures("admin")
    @pytest.mark.parametrize("change", [{"role": "operator"}, {"is_active": False}])
    async def test_the_last_active_admin_stays_one(
        self, api: httpx2.AsyncClient, use_session: UseSession, change: dict[str, object]
    ) -> None:
        other = make_user(username="other", role=UserRole.ADMIN)
        session = use_session(FakeSession([rows_result([other])]))
        response = await api.patch(f"{USERS}/{other.id}", json=change)
        assert response.status_code == 409
        assert response.json() == {"detail": "Holly needs at least one active admin."}
        assert other.role == "admin"
        assert other.is_active is True
        # The account and the active admins are read in one locked statement, so two admins
        # changing each other at once cannot leave none.
        assert_locked_afresh(session, 0)
        admins = "OR app_user.role = %(role_1)s::VARCHAR AND app_user.is_active IS true"
        assert admins in sql(session, 0)
        session.commit.assert_not_awaited()

    @pytest.mark.usefixtures("admin")
    async def test_the_admins_are_counted_as_the_locked_read_finds_them(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        # The second admin was deactivated by a change committed while this one waited for the
        # lock: the locked read finds it inactive, and it is not counted.
        other = make_user(username="other", role=UserRole.ADMIN)
        gone = make_user(username="gone", role=UserRole.ADMIN, is_active=False)
        use_session(FakeSession([rows_result([other, gone])]))
        response = await api.patch(f"{USERS}/{other.id}", json={"is_active": False})
        assert response.status_code == 409
        assert other.is_active is True

    @pytest.mark.usefixtures("admin", "audit_calls")
    async def test_an_inactive_admin_may_be_demoted_with_one_active_admin_left(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        # Demoting an admin already inactive takes no active admin away.
        idle = make_user(username="idle", role=UserRole.ADMIN, is_active=False)
        only = make_user(username="only", role=UserRole.ADMIN)
        use_session(stored(FakeSession([rows_result([idle, only])])))
        response = await api.patch(f"{USERS}/{idle.id}", json={"role": "analyst"})
        assert response.status_code == 200
        assert idle.role == "analyst"

    @pytest.mark.usefixtures("admin", "audit_calls")
    async def test_an_admin_may_go_while_another_active_admin_stays(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        other = make_user(username="other", role=UserRole.ADMIN)
        another = make_user(username="another", role=UserRole.ADMIN)
        use_session(stored(FakeSession([rows_result([another, other])])))
        response = await api.patch(f"{USERS}/{other.id}", json={"role": "analyst"})
        assert response.status_code == 200
        assert other.role == "analyst"

    async def test_an_admin_cannot_change_their_own_role_or_status_here(
        self, api: httpx2.AsyncClient, use_session: UseSession, admin: User
    ) -> None:
        session = use_session(FakeSession())
        response = await api.patch(f"{USERS}/{admin.id}", json={"is_active": False})
        assert response.status_code == 409
        session.execute.assert_not_awaited()

    @pytest.mark.usefixtures("admin")
    async def test_a_change_must_name_something(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        session = use_session(FakeSession())
        response = await api.patch(f"{USERS}/{uuid.uuid4()}", json={})
        assert response.status_code == 422
        session.execute.assert_not_awaited()
