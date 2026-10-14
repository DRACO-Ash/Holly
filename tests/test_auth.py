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

from app import dependencies
from app.api.v1.routes import auth
from app.config import get_settings
from app.core.rate_limit import LOGIN_ADDRESS_LIMIT, LOGIN_LIMIT
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
        # The attempt refused for want of a slot does not count against its username.
        assert len(LOGIN_LIMIT._hits["a"]) == 1
        assert not LOGIN_LIMIT._hits.get("b")

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
                dependencies._access_subject(None)
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
