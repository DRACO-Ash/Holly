"""Sign-in, refresh and sign-out (ADR-011), the token rules beneath them, and the audit row
each attempt writes. The audit chain and the revocation list are replaced with recorders, so
these tests read exactly what each route asked them to store."""

import asyncio
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app import dependencies
from app.api.v1.routes import auth
from app.config import get_settings
from app.core.rate_limit import LOGIN_ADDRESS_LIMIT, LOGIN_LIMIT
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    same_password,
    verify_password,
)
from app.dependencies import TOKEN_HEADER
from app.models.user import User, UserRole
from fakes import FakeSession, make_user, rows_result, scalar_result

UseSession = Callable[[FakeSession], FakeSession]

# Test-only sign-in values. bcrypt is real here, so the hash and the check are genuine.
KNOWN, WRONG, BEARER = "secret", "wrong", "bearer"


def user_lookup(user: User | None) -> FakeSession:
    """A session whose every query finds `user` (or nothing), the locked re-read of a password
    change included (services/accounts.py)."""
    session = FakeSession()
    session.execute.side_effect = None
    result = scalar_result(user)
    result.scalars.return_value.all.return_value = [user] if user is not None else []
    session.execute.return_value = result
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
        # An unknown username is not kept: it may be a password typed into the wrong box.
        expected = {"success": False, "reason": reason} | ({"username": "alice"} if user else {})
        assert call["detail"] == expected
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

    @pytest.mark.parametrize("known", [True, False], ids=["an account", "no account"])
    async def test_repeated_failures_are_refused_with_429_and_audited(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        known: bool,
    ) -> None:
        user = make_user(password=KNOWN) if known else None
        use_session(user_lookup(user))
        for _ in range(LOGIN_LIMIT.limit):
            LOGIN_LIMIT.record("alice")
        response = await api.post(
            "/api/v1/auth/login", json={"username": "alice", "password": KNOWN}
        )
        assert response.status_code == 429
        assert response.json()["detail"].startswith("Too many failed sign-ins. Try again in ")
        assert int(response.headers["retry-after"]) >= 1
        [call] = audit_calls
        assert call["user_id"] == (user.id if user else None)
        assert call["detail"] == {"success": False, "reason": "rate_limited"} | (
            {"username": "alice"} if known else {}
        )

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
        response = await api.get("/api/v1/auth/me", headers={TOKEN_HEADER: token})
        assert response.status_code == 200
        assert response.json()["username"] == "alice"
        assert "password_hash" not in response.json()

    @pytest.mark.parametrize("token", [None, "not.a.real.jwt", "", "   ", "Basic YWxpY2U6c2VjcmV0"])
    async def test_me_rejects_a_missing_or_malformed_credential(
        self, api: httpx2.AsyncClient, token: str | None
    ) -> None:
        headers = {TOKEN_HEADER: token} if token is not None else {}
        response = await api.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        # The marks section 10 of the operator manual tells Holly's own 401 by, against the
        # gateway's empty one.
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.headers["x-request-id"]
        assert response.json() == {"detail": "Could not validate credentials"}

    async def test_me_ignores_a_valid_token_in_authorization(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        # The App Store's gateway owns Authorization: Holly reads its token from its own header
        # alone, so a token anywhere else signs nobody in.
        user = make_user()
        session = use_session(user_lookup(user))
        token = create_access_token(str(user.id))
        response = await api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        session.execute.assert_not_awaited()

    async def test_me_holds_whatever_the_gateway_puts_in_authorization(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        headers = {
            TOKEN_HEADER: create_access_token(str(user.id)),
            "Authorization": "Bearer the.platforms.token",
        }
        response = await api.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["username"] == "alice"

    async def test_me_takes_the_token_alone_not_a_scheme_and_token(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        token = create_access_token(str(user.id))
        response = await api.get("/api/v1/auth/me", headers={TOKEN_HEADER: f"Bearer {token}"})
        assert response.status_code == 401

    async def test_me_rejects_refresh_token_used_as_access(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        refresh = create_refresh_token(str(user.id))
        response = await api.get("/api/v1/auth/me", headers={TOKEN_HEADER: refresh})
        assert response.status_code == 401

    async def test_me_rejects_a_subject_that_is_not_a_user_id(
        self, api: httpx2.AsyncClient
    ) -> None:
        token = create_access_token("not-a-uuid")
        response = await api.get("/api/v1/auth/me", headers={TOKEN_HEADER: token})
        assert response.status_code == 401

    @pytest.mark.parametrize("user", [None, make_user(is_active=False)])
    async def test_me_rejects_a_deleted_or_deactivated_user(
        self, api: httpx2.AsyncClient, use_session: UseSession, user: User | None
    ) -> None:
        use_session(user_lookup(user))
        token = create_access_token(str(uuid.uuid4()))
        response = await api.get("/api/v1/auth/me", headers={TOKEN_HEADER: token})
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

    @pytest.mark.parametrize("found", ["moved_on", "missing"])
    async def test_logout_refuses_a_token_whose_session_has_ended(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        revoked_jtis: set[str],
        audit_calls: list[dict[str, Any]],
        found: str,
    ) -> None:
        # A password change, a reset or a deactivation raised the version since the token was
        # issued: it works nowhere, and signing it out is not recorded as a sign-out.
        user = make_user(token_version=3)
        use_session(user_lookup(user if found == "moved_on" else None))
        refresh_token = create_refresh_token(str(user.id), version=2)
        response = await api.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
        assert response.status_code == 401
        assert _jti(refresh_token) not in revoked_jtis
        [call] = audit_calls
        assert call["detail"] == {"success": False, "reason": "stale_token"}
        assert call["user_id"] == user.id


def recording_check(checked: list[str], result: bool = False) -> Callable[[str, str], bool]:
    """A stand-in for verify_password that notes each hash it is asked to check."""

    def check(_plain: str, hashed: str) -> bool:
        checked.append(hashed)
        return result

    return check


class TestSignInUnderLoad:
    """bcrypt runs on worker threads, a few checks at a time, behind a limit per address, so a
    burst of sign-ins can neither stall nor crash the one worker."""

    async def test_an_unknown_username_still_costs_a_password_check(
        self, api: httpx2.AsyncClient, use_session: UseSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        checked: list[str] = []
        monkeypatch.setattr(auth, "verify_password", recording_check(checked))
        use_session(user_lookup(None))
        response = await api.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": KNOWN}
        )
        assert response.status_code == 401
        assert checked == [auth._dummy_hash()]

    async def test_attempts_are_limited_per_address_before_anything_is_checked(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        checked: list[str] = []
        monkeypatch.setattr(auth, "verify_password", recording_check(checked))
        session = use_session(user_lookup(None))
        for _ in range(LOGIN_ADDRESS_LIMIT.limit):
            LOGIN_ADDRESS_LIMIT.record("127.0.0.1")
        response = await api.post(
            "/api/v1/auth/login", json={"username": "alice", "password": KNOWN}
        )
        assert response.status_code == 429
        assert response.json()["detail"].startswith(
            "Too many sign-in attempts from this address. Try again in "
        )
        assert int(response.headers["retry-after"]) >= 1
        assert checked == []
        assert audit_calls == []
        session.execute.assert_not_awaited()

    async def test_a_sign_in_beyond_the_concurrent_checks_is_refused_at_once(
        self, api: httpx2.AsyncClient, use_session: UseSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(auth, "_PASSWORD_CHECK_SLOTS", threading.BoundedSemaphore(1))
        entered, release = threading.Event(), threading.Event()

        def held_check(_plain: str, _hashed: str) -> bool:
            entered.set()
            release.wait(5)
            return False

        monkeypatch.setattr(auth, "verify_password", held_check)
        use_session(user_lookup(None))
        body = {"password": KNOWN}
        first = asyncio.create_task(api.post("/api/v1/auth/login", json=body | {"username": "a"}))
        assert await asyncio.to_thread(entered.wait, 5)
        second = await api.post("/api/v1/auth/login", json=body | {"username": "b"})
        release.set()
        assert second.status_code == 503
        assert second.json() == {"detail": "Sign-in is busy. Try again in a moment."}
        assert second.headers["retry-after"] == "1"
        assert (await first).status_code == 401
        # The held check gave its slot back when it ended.
        assert auth._PASSWORD_CHECK_SLOTS.acquire(blocking=False)
        # The attempt refused for want of a slot does not count against its username, nor
        # take a place among the usernames the limiter remembers.
        assert len(LOGIN_LIMIT._hits["a"]) == 1
        assert "b" not in LOGIN_LIMIT._hits

    async def test_four_checks_run_at_once_and_a_fifth_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The module's own slots, not a stand-in.
        entered, release = threading.Semaphore(0), threading.Event()

        def held_check(_plain: str, _hashed: str) -> bool:
            entered.release()
            release.wait(5)
            return False

        monkeypatch.setattr(auth, "verify_password", held_check)
        use_session(user_lookup(None))
        held = [
            asyncio.create_task(
                api.post("/api/v1/auth/login", json={"username": f"user{n}", "password": KNOWN})
            )
            for n in range(4)
        ]
        for _ in held:
            assert await asyncio.to_thread(entered.acquire, True, 5)
        fifth = await api.post("/api/v1/auth/login", json={"username": "user4", "password": KNOWN})
        release.set()
        assert fifth.status_code == 503
        assert [response.status_code for response in await asyncio.gather(*held)] == [401] * 4

    async def test_each_check_counts_before_it_runs_so_concurrent_guesses_stop_at_the_limit(
        self, api: httpx2.AsyncClient, use_session: UseSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for _ in range(9):
            LOGIN_LIMIT.record("alice")
        entered, release = threading.Event(), threading.Event()
        checked: list[str] = []

        def held_check(_plain: str, hashed: str) -> bool:
            checked.append(hashed)
            entered.set()
            release.wait(5)
            return False

        monkeypatch.setattr(auth, "verify_password", held_check)
        use_session(user_lookup(make_user(password=KNOWN)))
        body = {"username": "alice", "password": WRONG}
        tenth = asyncio.create_task(api.post("/api/v1/auth/login", json=body))
        assert await asyncio.to_thread(entered.wait, 5)
        eleventh = await api.post("/api/v1/auth/login", json=body)
        release.set()
        assert eleventh.status_code == 429
        assert (await tenth).status_code == 401
        assert len(checked) == 1

    async def test_attempts_sent_together_at_the_last_place_get_one_check_between_them(
        self, api: httpx2.AsyncClient, use_session: UseSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Nothing awaits between the limit test and the count, so of five attempts that all
        # arrive while one place is left, one is checked and four are refused.
        for _ in range(9):
            LOGIN_LIMIT.record("alice")
        entered, release = threading.Event(), threading.Event()
        checked: list[str] = []

        def held_check(_plain: str, hashed: str) -> bool:
            checked.append(hashed)
            entered.set()
            release.wait(5)
            return False

        monkeypatch.setattr(auth, "verify_password", held_check)
        use_session(user_lookup(make_user(password=KNOWN)))
        body = {"username": "alice", "password": WRONG}
        attempts = [
            asyncio.create_task(api.post("/api/v1/auth/login", json=body)) for _ in range(5)
        ]
        assert await asyncio.to_thread(entered.wait, 5)
        release.set()
        statuses = sorted(response.status_code for response in await asyncio.gather(*attempts))
        assert statuses == [401, 429, 429, 429, 429]
        assert len(checked) == 1

    async def test_a_check_cancelled_before_it_reaches_a_thread_still_gives_its_slot_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # One worker thread, kept busy, so the check queues behind it; then its request is
        # cancelled. The check must still run, as only the check gives its slot back.
        checked: list[str] = []
        monkeypatch.setattr(auth, "verify_password", recording_check(checked))
        slots = threading.BoundedSemaphore(1)
        monkeypatch.setattr(auth, "_PASSWORD_CHECK_SLOTS", slots)
        loop = asyncio.get_running_loop()
        one_thread = ThreadPoolExecutor(max_workers=1)
        loop.set_default_executor(one_thread)
        release = threading.Event()
        busy = loop.run_in_executor(None, release.wait, 5)
        check = asyncio.create_task(auth._check_password(None, "alice", KNOWN))
        await asyncio.sleep(0)
        check.cancel()
        with pytest.raises(asyncio.CancelledError):
            await check
        release.set()
        await busy
        one_thread.shutdown(wait=True)
        assert slots.acquire(blocking=False), "the cancelled check never gave its slot back"
        assert checked == [auth._dummy_hash()]

    async def test_password_checks_leave_the_event_loop_free(
        self, api: httpx2.AsyncClient, use_session: UseSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entered = threading.Event()

        def slow_check(_plain: str, _hashed: str) -> bool:
            entered.set()
            time.sleep(0.5)
            return False

        monkeypatch.setattr(auth, "verify_password", slow_check)
        use_session(user_lookup(None))
        logins = [
            asyncio.create_task(
                api.post("/api/v1/auth/login", json={"username": f"user{n}", "password": KNOWN})
            )
            for n in range(3)
        ]
        assert await asyncio.to_thread(entered.wait, 5)
        started = time.perf_counter()
        probe = await api.get("/livez")
        elapsed = time.perf_counter() - started
        assert probe.status_code == 200
        assert elapsed < 0.25, f"/livez waited {elapsed:.2f}s behind the password checks"
        assert [response.status_code for response in await asyncio.gather(*logins)] == [401] * 3


class TestRefusalsAreNotShared:
    def test_each_refusal_is_a_new_exception_whose_traceback_does_not_grow(self) -> None:
        caught: list[HTTPException] = []
        for _ in range(2):
            with pytest.raises(HTTPException) as raised:
                dependencies._access_claims(None)
            caught.append(raised.value)
        first, second = caught
        assert first is not second
        assert len(traceback.extract_tb(second.__traceback__)) == len(
            traceback.extract_tb(first.__traceback__)
        )

    @pytest.mark.parametrize(
        "refusal",
        [auth._invalid_credentials, auth._invalid_refresh, dependencies._credentials_error],
    )
    def test_every_refusal_factory_builds_a_fresh_401(
        self, refusal: Callable[[], HTTPException]
    ) -> None:
        first, second = refusal(), refusal()
        assert first is not second
        assert first.status_code == second.status_code == 401


ME = "/api/v1/auth/me"
CHANGE_ROUTE = "/api/v1/auth/password"
# A new password of the length Holly requires; test-only.
NEW = "a-new-test-password"


def token_with(user: User, *, version: object = None, kind: str = "access") -> str:
    """A token for `user` whose `ver` claim is `version`, or that has none when it is None."""
    claims: dict[str, Any] = {
        "sub": str(user.id),
        "type": kind,
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    if version is not None:
        claims["ver"] = version
    return jwt.encode(claims, get_settings().app_secret_key.get_secret_value(), algorithm="HS256")


def signed_in_as(user: User) -> dict[str, str]:
    return {TOKEN_HEADER: create_access_token(str(user.id), version=user.token_version)}


def copy_of(user: User, **changes: Any) -> User:
    """The same account as a second read finds it, with any change committed meanwhile."""
    fresh = make_user(
        username=user.username,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        token_version=user.token_version,
    )
    fresh.id = user.id
    fresh.password_hash = user.password_hash
    for field, value in changes.items():
        setattr(fresh, field, value)
    return fresh


class TestTokenVersion:
    async def test_a_token_from_before_the_user_s_version_changed_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user(token_version=2)
        use_session(user_lookup(user))
        stale = {TOKEN_HEADER: create_access_token(str(user.id), version=1)}
        assert (await api.get(ME, headers=stale)).status_code == 401
        assert (await api.get(ME, headers=signed_in_as(user))).status_code == 200

    async def test_a_token_issued_before_versions_existed_reads_as_version_0(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        unversioned = {TOKEN_HEADER: token_with(user)}
        assert (await api.get(ME, headers=unversioned)).status_code == 200
        user.token_version = 1
        assert (await api.get(ME, headers=unversioned)).status_code == 401

    @pytest.mark.parametrize("version", ["0", True, False, 0.0, [0]])
    async def test_a_version_that_is_not_a_whole_number_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, version: object
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        response = await api.get(ME, headers={TOKEN_HEADER: token_with(user, version=version)})
        assert response.status_code == 401

    async def test_sign_in_issues_both_tokens_under_the_user_s_version(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user(password=KNOWN, token_version=3)
        use_session(user_lookup(user))
        response = await api.post(
            "/api/v1/auth/login", json={"username": "alice", "password": KNOWN}
        )
        assert response.status_code == 200
        for name in ("access_token", "refresh_token"):
            decoded = decode_token(response.json()[name])
            assert decoded is not None
            assert decoded["ver"] == 3

    async def test_a_refresh_token_from_before_the_version_changed_is_refused(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        revoked_jtis: set[str],
    ) -> None:
        user = make_user(token_version=1)
        use_session(user_lookup(user))
        stale = create_refresh_token(str(user.id), version=0)
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": stale})
        assert response.status_code == 401
        assert audit_calls[-1]["detail"] == {"success": False, "reason": "stale_token"}
        assert _jti(stale) not in revoked_jtis
        current = create_refresh_token(str(user.id), version=1)
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": current})
        assert response.status_code == 200
        decoded = decode_token(response.json()["access_token"])
        assert decoded is not None
        assert decoded["ver"] == 1

    async def test_a_refresh_token_whose_version_is_not_a_number_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        user = make_user()
        use_session(user_lookup(user))
        token = token_with(user, version="0", kind="refresh")
        response = await api.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert response.status_code == 401
        assert audit_calls[-1]["detail"] == {"success": False, "reason": "invalid_token"}


class TestPasswordChangeDue:
    async def test_until_it_is_changed_only_me_and_the_password_route_answer(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user(must_change_password=True)
        session = use_session(user_lookup(user))
        me = await api.get(ME, headers=signed_in_as(user))
        assert me.status_code == 200
        assert me.json()["must_change_password"] is True
        refused = await api.get("/api/v1/notifications", headers=signed_in_as(user))
        assert refused.status_code == 403
        assert refused.json() == {"detail": dependencies.CHANGE_DUE}
        # Only the two user lookups ran: the notifications route itself never did.
        assert session.execute.await_count == 2

    async def test_a_user_with_no_change_due_is_not_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user(role=UserRole.ADMIN)
        use_session(user_lookup(user))
        me = await api.get(ME, headers=signed_in_as(user))
        assert me.json()["must_change_password"] is False
        # Through the gate on a route that needs it: the fake's every query finds no rows.
        assert (await api.get("/api/v1/users", headers=signed_in_as(user))).status_code == 200


class TestChangePassword:
    async def test_a_change_ends_every_earlier_session_and_issues_a_new_pair(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        user = make_user(password=KNOWN, must_change_password=True, token_version=4)
        session = use_session(user_lookup(user))
        before = signed_in_as(user)
        response = await api.post(
            CHANGE_ROUTE, json={"current_password": KNOWN, "new_password": NEW}, headers=before
        )
        assert response.status_code == 200
        assert user.token_version == 5
        assert user.must_change_password is False
        assert verify_password(NEW, user.password_hash)
        assert audit_calls[-1]["action_type"] == "auth.user.password_change"
        assert audit_calls[-1]["detail"] == {"success": True}
        assert audit_calls[-1]["user_id"] == user.id
        session.commit.assert_awaited()
        assert (await api.get(ME, headers=before)).status_code == 401
        after = {TOKEN_HEADER: response.json()["access_token"]}
        assert (await api.get(ME, headers=after)).status_code == 200
        refresh = decode_token(response.json()["refresh_token"])
        assert refresh is not None
        assert refresh["ver"] == 5
        # The user was read again under a lock before the change was written: the second query,
        # after the token's own.
        locked = session.execute.await_args_list[1].args[0]
        assert locked.get_execution_options()["populate_existing"] is True
        dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
        rendered = str(locked.compile(dialect=dialect))
        assert rendered.endswith("ORDER BY app_user.id FOR NO KEY UPDATE")

    async def test_the_change_is_written_to_the_row_the_locked_read_found(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user(password=KNOWN, token_version=4)
        fresh = copy_of(user)
        use_session(FakeSession([scalar_result(user), rows_result([fresh])]))
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": KNOWN, "new_password": NEW},
            headers=signed_in_as(user),
        )
        assert response.status_code == 200
        assert fresh.token_version == 5
        assert verify_password(NEW, fresh.password_hash)
        access = decode_token(response.json()["access_token"])
        assert access is not None
        assert access["ver"] == 5

    @pytest.mark.parametrize(
        ("meanwhile", "reason"),
        [
            # An admin reset the password while this change ran its bcrypt rounds.
            ({"token_version": 5, "must_change_password": True}, "stale_token"),
            # The hash changed without the version: refused all the same.
            ({"password_hash": "another-hash"}, "stale_token"),
            # An admin deactivated the account meanwhile.
            ({"is_active": False}, "inactive_user"),
        ],
    )
    async def test_a_change_made_meanwhile_is_not_undone(
        self,
        api: httpx2.AsyncClient,
        use_session: UseSession,
        audit_calls: list[dict[str, Any]],
        meanwhile: dict[str, Any],
        reason: str,
    ) -> None:
        user = make_user(password=KNOWN, token_version=4)
        fresh = copy_of(user, **meanwhile)
        session = use_session(FakeSession([scalar_result(user), rows_result([fresh])]))
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": KNOWN, "new_password": NEW},
            headers=signed_in_as(user),
        )
        # 401, as for any ended session: the dashboard's refresh fails too, and it signs out.
        assert response.status_code == 401
        assert response.json() == {"detail": "Could not validate credentials"}
        assert audit_calls[-1]["detail"] == {"success": False, "reason": reason}
        for field, value in meanwhile.items():
            assert getattr(fresh, field) == value
        assert fresh.token_version == meanwhile.get("token_version", 4)
        assert not verify_password(NEW, user.password_hash)
        session.commit.assert_awaited_once()

    async def test_an_account_gone_meanwhile_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        user = make_user(password=KNOWN)
        use_session(FakeSession([scalar_result(user), rows_result([])]))
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": KNOWN, "new_password": NEW},
            headers=signed_in_as(user),
        )
        assert response.status_code == 401
        assert audit_calls[-1]["detail"] == {"success": False, "reason": "inactive_user"}

    async def test_a_wrong_current_password_is_refused_audited_and_counted(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        user = make_user(password=KNOWN)
        use_session(user_lookup(user))
        body = {"current_password": WRONG, "new_password": NEW}
        response = await api.post(CHANGE_ROUTE, json=body, headers=signed_in_as(user))
        # 400, so the dashboard keeps the session rather than refreshing and signing out.
        assert response.status_code == 400
        assert response.json() == {"detail": "The current password is not correct."}
        assert audit_calls[-1]["detail"] == {"success": False, "reason": "wrong_password"}
        assert user.token_version == 0
        assert verify_password(KNOWN, user.password_hash)
        for _ in range(9):
            await api.post(CHANGE_ROUTE, json=body, headers=signed_in_as(user))
        # The guesses count against the same per-username limit as sign-in.
        limited = await api.post(CHANGE_ROUTE, json=body, headers=signed_in_as(user))
        assert limited.status_code == 429
        assert audit_calls[-1]["detail"] == {"success": False, "reason": "rate_limited"}

    async def test_a_right_current_password_clears_the_failures_counted(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        user = make_user(password=KNOWN)
        use_session(user_lookup(user))
        LOGIN_LIMIT.record("alice")
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": KNOWN, "new_password": NEW},
            headers=signed_in_as(user),
        )
        assert response.status_code == 200
        assert LOGIN_LIMIT.wait_time("alice") == 0
        for _ in range(9):
            LOGIN_LIMIT.record("alice")
        assert LOGIN_LIMIT.wait_time("alice") == 0

    async def test_the_current_password_again_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, audit_calls: list[dict[str, Any]]
    ) -> None:
        user = make_user(password=NEW, must_change_password=True)
        use_session(user_lookup(user))
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": NEW, "new_password": NEW},
            headers=signed_in_as(user),
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Choose a new password, not the current one."}
        assert user.must_change_password is True
        assert user.token_version == 0
        assert audit_calls[-1]["detail"] == {"success": False, "reason": "same_password"}

    async def test_a_change_beyond_the_concurrent_checks_is_refused_in_its_own_words(
        self, api: httpx2.AsyncClient, use_session: UseSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Every slot is taken: the page says so plainly, not that sign-in is busy.
        monkeypatch.setattr(auth, "_PASSWORD_CHECK_SLOTS", threading.BoundedSemaphore(1))
        assert auth._PASSWORD_CHECK_SLOTS.acquire(blocking=False)
        user = make_user(password=KNOWN)
        use_session(user_lookup(user))
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": KNOWN, "new_password": NEW},
            headers=signed_in_as(user),
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Password checks are busy. Try again in a moment."}
        assert user.token_version == 0

    async def test_a_password_bcrypt_would_read_as_the_current_one_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession
    ) -> None:
        # bcrypt reads the first 72 bytes alone, so these two are one password to it.
        current, new = "p" * 72 + "-one", "p" * 72 + "-two"
        user = make_user(password=current)
        use_session(user_lookup(user))
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": current, "new_password": new},
            headers=signed_in_as(user),
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Choose a new password, not the current one."}

    @pytest.mark.parametrize("new_password", ["p" * 11, " " * 12, "p" * 1025, "p" * 12 + "\x00"])
    async def test_a_new_password_holly_would_not_set_is_refused(
        self, api: httpx2.AsyncClient, use_session: UseSession, new_password: str
    ) -> None:
        user = make_user(password=KNOWN)
        session = use_session(user_lookup(user))
        response = await api.post(
            CHANGE_ROUTE,
            json={"current_password": KNOWN, "new_password": new_password},
            headers=signed_in_as(user),
        )
        assert response.status_code == 422
        assert new_password not in response.text
        # Nor its length.
        assert f"not {len(new_password)}" not in response.text
        session.commit.assert_not_awaited()


def test_two_passwords_are_one_to_bcrypt_when_their_first_72_bytes_match() -> None:
    assert same_password("p" * 72 + "a", "p" * 72 + "b")
    # Counted in UTF-8 bytes: 36 two-byte letters fill the 72.
    assert same_password("é" * 36 + "a", "é" * 36 + "b")
    assert not same_password("p" * 71 + "a", "p" * 71 + "b")
    assert not same_password("p" * 12, "q" * 12)
