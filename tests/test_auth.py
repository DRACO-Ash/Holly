"""Sign-in, refresh and sign-out (ADR-011), the token rules beneath them, and the audit row
each attempt writes. The audit chain and the revocation list are replaced with recorders, so
these tests read exactly what each route asked them to store."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import jwt
import pytest

from app.config import get_settings
from app.core.rate_limit import LOGIN_LIMIT
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from fakes import FakeSession, make_user, scalar_result

UseSession = Callable[[FakeSession], FakeSession]

# Test-only sign-in values. bcrypt is real here, so the hash and the check are genuine.
KNOWN, WRONG, BEARER = "secret", "wrong", "bearer"


def user_lookup(user: User | None) -> FakeSession:
    """A session whose every query finds `user` (or nothing)."""
    session = FakeSession()
    session.execute.side_effect = None
    session.execute.return_value = scalar_result(user)
    return session


@pytest.fixture(autouse=True)
def audit_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def record(_db: object, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("app.api.v1.routes.auth.write_audit", AsyncMock(side_effect=record))
    return calls


@pytest.fixture(autouse=True)
def revoked_jtis(monkeypatch: pytest.MonkeyPatch) -> set[str]:
    revoked: set[str] = set()

    def is_revoked(_db: object, jti: str) -> bool:
        return jti in revoked

    def revoke(_db: object, *, jti: str, expires_at: datetime, **_claims: object) -> None:
        assert expires_at > datetime.now(UTC)
        revoked.add(jti)

    monkeypatch.setattr("app.api.v1.routes.auth.is_revoked", AsyncMock(side_effect=is_revoked))
    monkeypatch.setattr("app.api.v1.routes.auth.revoke", AsyncMock(side_effect=revoke))
    return revoked


def _jti(token: str) -> str:
    decoded = decode_token(token)
    assert decoded is not None
    return str(decoded["jti"])


class TestPasswordsAndTokens:
    def test_hash_and_verify_password(self) -> None:
        hashed = hash_password("hunter2")
        assert verify_password("hunter2", hashed)
        assert not verify_password("wrong", hashed)

    def test_a_malformed_hash_never_verifies(self) -> None:
        assert not verify_password("hunter2", "not-a-bcrypt-hash")

    def test_only_the_first_72_bytes_of_a_password_count(self) -> None:
        # bcrypt's own limit; Holly truncates rather than letting bcrypt raise.
        hashed = hash_password("a" * 72 + "first-tail")
        assert verify_password("a" * 72 + "other-tail", hashed)

    def test_access_token_round_trip(self) -> None:
        subject = str(uuid.uuid4())
        decoded = decode_token(create_access_token(subject))
        assert decoded is not None
        assert decoded["sub"] == subject
        assert decoded["type"] == "access"

    def test_refresh_token_carries_type_refresh(self) -> None:
        decoded = decode_token(create_refresh_token(str(uuid.uuid4())))
        assert decoded is not None
        assert decoded["type"] == "refresh"

    def test_every_token_has_its_own_id(self) -> None:
        subject = str(uuid.uuid4())
        assert _jti(create_refresh_token(subject)) != _jti(create_refresh_token(subject))

    def test_decode_token_returns_none_on_garbage(self) -> None:
        assert decode_token("not.a.real.jwt") is None

    def test_decode_token_returns_none_on_expired_token(self) -> None:
        token = create_access_token(str(uuid.uuid4()), expires_delta=timedelta(seconds=-10))
        assert decode_token(token) is None

    def test_a_token_signed_with_another_key_is_refused(self) -> None:
        claims = {"sub": "x", "type": "access", "jti": "j", "exp": datetime.now(UTC) + timedelta(1)}
        forged = jwt.encode(claims, "another-key-entirely-" + "k" * 32, algorithm="HS256")
        assert decode_token(forged) is None

    def test_a_token_using_another_algorithm_is_refused(self) -> None:
        key = get_settings().app_secret_key.get_secret_value()
        claims = {"sub": "x", "type": "access", "jti": "j", "exp": datetime.now(UTC) + timedelta(1)}
        assert decode_token(jwt.encode(claims, key, algorithm="HS512")) is None

    def test_an_unsigned_token_is_refused(self) -> None:
        claims = {"sub": "x", "type": "access", "jti": "j", "exp": datetime.now(UTC) + timedelta(1)}
        assert decode_token(jwt.encode(claims, key=None, algorithm="none")) is None

    @pytest.mark.parametrize("missing", ["exp", "sub", "type", "jti"])
    def test_a_token_missing_a_required_claim_is_refused(self, missing: str) -> None:
        key = get_settings().app_secret_key.get_secret_value()
        claims = {"sub": "x", "type": "access", "jti": "j", "exp": datetime.now(UTC) + timedelta(1)}
        del claims[missing]
        assert decode_token(jwt.encode(claims, key, algorithm="HS256")) is None


class TestLogin:
    async def test_login_returns_tokens_on_success(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        use_session(user_lookup(make_user(password=KNOWN)))
        response = await api.post(
            "/api/v1/auth/login", json={"username": "alice", "password": KNOWN}
        )
        assert response.status_code == 200
        body = response.json()
        assert decode_token(body["access_token"]) is not None
        assert decode_token(body["refresh_token"]) is not None
        assert body["token_type"] == BEARER

    async def test_the_username_is_matched_trimmed_and_lowercase(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        use_session(user_lookup(make_user(password=KNOWN)))
        response = await api.post(
            "/api/v1/auth/login", json={"username": "  Alice ", "password": KNOWN}
        )
        assert response.status_code == 200
        assert audit_calls[0]["detail"]["username"] == "alice"

    @pytest.mark.parametrize(
        ("user", "password", "reason"),
        [
            (make_user(password=KNOWN), WRONG, "wrong_password"),
            (None, KNOWN, "unknown_user"),
            (make_user(password=KNOWN, is_active=False), KNOWN, "inactive_user"),
        ],
    )
    async def test_a_failed_sign_in_is_401_and_audited_with_its_reason(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        user: User | None,
        password: str,
        reason: str,
    ) -> None:
        session = use_session(user_lookup(user))
        response = await api.post(
            "/api/v1/auth/login", json={"username": "alice", "password": password}
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid username or password"}
        [call] = audit_calls
        assert call["action_type"] == "auth.user.login"
        assert call["entity_type"] == "user"
        assert call["user_id"] == (user.id if user else None)
        assert call["entity_id"] == (str(user.id) if user else None)
        assert call["detail"] == {"success": False, "username": "alice", "reason": reason}
        session.commit.assert_awaited()

    async def test_login_success_emits_audit_row(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        user = make_user(password=KNOWN)
        use_session(user_lookup(user))
        await api.post("/api/v1/auth/login", json={"username": "alice", "password": KNOWN})
        [call] = audit_calls
        assert call["action_type"] == "auth.user.login"
        assert call["entity_id"] == str(user.id)
        assert call["user_id"] == user.id
        assert call["ip_address"] == "127.0.0.1"
        assert call["detail"] == {"success": True, "username": "alice"}

    async def test_repeated_failures_are_refused_with_429_and_audited(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        use_session(user_lookup(None))
        for _ in range(LOGIN_LIMIT.limit):
            LOGIN_LIMIT.record("alice")
        response = await api.post(
            "/api/v1/auth/login", json={"username": "alice", "password": KNOWN}
        )
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) >= 1
        assert audit_calls[-1]["detail"] == {
            "success": False,
            "username": "alice",
            "reason": "rate_limited",
        }

    async def test_each_failure_counts_and_a_success_clears_the_count(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        use_session(user_lookup(make_user(password=KNOWN)))
        await api.post("/api/v1/auth/login", json={"username": "alice", "password": WRONG})
        assert LOGIN_LIMIT.wait_time("alice") == 0
        assert len(LOGIN_LIMIT._hits["alice"]) == 1
        await api.post("/api/v1/auth/login", json={"username": "alice", "password": KNOWN})
        assert "alice" not in LOGIN_LIMIT._hits

    @pytest.mark.parametrize(
        "body",
        [
            {"username": "alice"},
            {"password": KNOWN},
            {"username": "", "password": KNOWN},
            {"username": "a" * 51, "password": KNOWN},
            {"username": "alice", "password": "p" * 1025},
        ],
    )
    async def test_a_malformed_sign_in_is_422(
        self, api: httpx2.AsyncClient, body: dict[str, str]
    ) -> None:
        assert (await api.post("/api/v1/auth/login", json=body)).status_code == 422


class TestMe:
    async def test_me_returns_current_user_for_valid_token(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        token = create_access_token(str(user.id))
        response = await api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["username"] == "alice"
        assert "password_hash" not in response.json()

    @pytest.mark.parametrize(
        "authorization",
        [None, "Bearer not.a.real.jwt", "Basic YWxpY2U6c2VjcmV0", "Bearer"],
    )
    async def test_me_rejects_a_missing_or_malformed_credential(
        self, api: httpx2.AsyncClient, authorization: str | None
    ) -> None:
        headers = {"Authorization": authorization} if authorization else {}
        response = await api.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_me_rejects_refresh_token_used_as_access(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        refresh = create_refresh_token(str(user.id))
        response = await api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"})
        assert response.status_code == 401

    async def test_me_rejects_a_subject_that_is_not_a_user_id(
        self, api: httpx2.AsyncClient
    ) -> None:
        token = create_access_token("not-a-uuid")
        response = await api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    @pytest.mark.parametrize("user", [None, make_user(is_active=False)])
    async def test_me_rejects_a_deleted_or_deactivated_user(
        self, api: httpx2.AsyncClient, use_session: UseSession, user: User | None
    ) -> None:
        use_session(user_lookup(user))
        token = create_access_token(str(uuid.uuid4()))
        response = await api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    async def test_elsets_ingest_requires_auth(self, api: httpx2.AsyncClient) -> None:
        response = await api.post(
            "/api/v1/elsets/ingest", json={"epoch_gte": "2025-01-01T00:00:00Z"}
        )
        assert response.status_code == 401


class TestRefresh:
    async def test_refresh_returns_new_tokens_and_revokes_the_old_one(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        revoked_jtis: set[str],
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        refresh_token = create_refresh_token(str(user.id))
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        body = response.json()
        assert body["refresh_token"] != refresh_token
        assert body["token_type"] == BEARER
        assert _jti(refresh_token) in revoked_jtis
        [call] = audit_calls
        assert call["action_type"] == "auth.token.refresh"
        assert call["user_id"] == user.id
        assert call["detail"] == {"success": True}

    async def test_refresh_rejects_access_token_used_as_refresh(
        self, api: httpx2.AsyncClient, audit_calls: list[dict[str, Any]]
    ) -> None:
        access = create_access_token(str(uuid.uuid4()))
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert response.status_code == 401
        assert audit_calls[0]["detail"]["reason"] == "invalid_token"

    async def test_refresh_invalid_token_emits_audit_with_no_user(
        self, api: httpx2.AsyncClient, audit_calls: list[dict[str, Any]]
    ) -> None:
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
        assert response.status_code == 401
        [call] = audit_calls
        assert call["action_type"] == "auth.token.refresh"
        assert call["user_id"] is None
        assert call["detail"] == {"success": False, "reason": "invalid_token"}

    async def test_refresh_rejects_a_subject_that_is_not_a_user_id(
        self, api: httpx2.AsyncClient, audit_calls: list[dict[str, Any]]
    ) -> None:
        token = create_refresh_token("not-a-uuid")
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert response.status_code == 401
        assert audit_calls[0]["detail"]["reason"] == "malformed_subject"

    async def test_refresh_rejects_revoked_token(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        revoked_jtis: set[str],
        audit_calls: list[dict[str, Any]],
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        refresh_token = create_refresh_token(str(user.id))
        revoked_jtis.add(_jti(refresh_token))
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 401
        assert audit_calls[0]["detail"]["reason"] == "revoked_token"

    @pytest.mark.parametrize("found", [False, True])
    async def test_refresh_rejects_a_deleted_or_deactivated_user(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        revoked_jtis: set[str],
        audit_calls: list[dict[str, Any]],
        found: bool,
    ) -> None:
        user = make_user(is_active=False)
        use_session(user_lookup(user if found else None))
        refresh_token = create_refresh_token(str(user.id))
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 401
        assert audit_calls[0]["detail"] == {"success": False, "reason": "inactive_user"}
        assert audit_calls[0]["user_id"] == (user.id if found else None)
        assert not revoked_jtis


class TestLogout:
    async def test_logout_revokes_refresh_and_returns_204(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        revoked_jtis: set[str],
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        refresh_token = create_refresh_token(str(user.id))
        response = await api.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        assert response.status_code == 204
        assert _jti(refresh_token) in revoked_jtis
        [call] = audit_calls
        assert call["action_type"] == "auth.user.logout"
        assert call["user_id"] == user.id
        assert call["detail"] == {"success": True}

    @pytest.mark.parametrize("body", [{}, {"refresh_token": ""}, {"refresh_token": "t" * 4097}])
    @pytest.mark.parametrize("path", ["/api/v1/auth/logout", "/api/v1/auth/refresh"])
    async def test_a_missing_or_oversized_refresh_token_is_422(
        self, api: httpx2.AsyncClient, path: str, body: dict[str, str]
    ) -> None:
        assert (await api.post(path, json=body)).status_code == 422

    async def test_logout_rejects_garbage_refresh_token(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        use_session(user_lookup(None))
        response = await api.post("/api/v1/auth/logout", json={"refresh_token": "not.a.real.jwt"})
        assert response.status_code == 401
        assert audit_calls[0]["action_type"] == "auth.user.logout"
        assert audit_calls[0]["detail"]["reason"] == "invalid_token"

    async def test_logout_rejects_already_revoked_refresh(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        revoked_jtis: set[str],
        audit_calls: list[dict[str, Any]],
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        refresh_token = create_refresh_token(str(user.id))
        revoked_jtis.add(_jti(refresh_token))
        response = await api.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        assert response.status_code == 401
        assert audit_calls[0]["detail"]["reason"] == "already_revoked"
        assert audit_calls[0]["user_id"] == user.id
