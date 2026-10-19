"""Sign-in, token refresh and sign-out, each written to the audit chain.

Sign-in attempts are limited per client address before any password is checked, and per
username (core/rate_limit.py): each checked attempt counts against its username before the
check starts, and a success clears the count. Every checked attempt costs one bcrypt check,
against a dummy hash for an unknown username, so the response time does not reveal which
usernames exist. bcrypt runs on worker threads, a few at a time, so a burst of sign-ins cannot
stall the one worker. Refresh tokens rotate: each one
works once, and its id joins the block-list when it is used or signed out (ADR-011).
"""

import asyncio
import logging
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.net import client_ip
from app.core.rate_limit import LOGIN_ADDRESS_LIMIT, LOGIN_LIMIT
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.dependencies import CurrentUser, DbSession
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserRead,
)
from app.services.audit import write_audit
from app.services.token_revocation import is_revoked, revoke

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# The audit actions these routes write.
AUDIT_LOGIN = "auth.user.login"
AUDIT_REFRESH = "auth.token.refresh"
AUDIT_LOGOUT = "auth.user.logout"

# bcrypt is deliberately slow, a few hundred milliseconds a check. At most this many checks run
# at once, each on a worker thread; a sign-in beyond them is refused at once, not queued.
MAX_CONCURRENT_PASSWORD_CHECKS = 4
_PASSWORD_CHECK_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_PASSWORD_CHECKS)


# Each refusal is a new exception: raising one shared instance again would add every request's
# frames to its traceback and keep them alive for the life of the process.
def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
    )


def _invalid_refresh() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")


@dataclass(frozen=True)
class _RefreshClaims:
    user_id: UUID
    jti: str
    expires_at: datetime


class _RefreshRejectedError(Exception):
    """A refresh token that cannot be used, with the reason the audit chain records."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    # The hash of a random value nobody holds, so an unknown username still costs a real check.
    return hash_password(secrets.token_urlsafe(32))


async def _audit(
    db: AsyncSession,
    action_type: str,
    *,
    user_id: UUID | None,
    ip: str | None,
    detail: dict[str, Any],
) -> None:
    await write_audit(
        db,
        action_type=action_type,
        entity_type="user",
        entity_id=str(user_id) if user_id is not None else None,
        user_id=user_id,
        ip_address=ip,
        detail=detail,
    )
    await db.commit()


def _login_failure(user: User | None, password: str) -> str | None:
    password_ok = verify_password(password, user.password_hash if user else _dummy_hash())
    if user is None:
        return "unknown_user"
    if not user.is_active:
        return "inactive_user"
    return None if password_ok else "wrong_password"


def _login_failure_in_slot(user: User | None, password: str) -> str | None:
    """_login_failure on a worker thread, giving its slot back when the check ends, even when
    the request that asked for it has gone. Nothing else gives the slot back."""
    try:
        return _login_failure(user, password)
    finally:
        _PASSWORD_CHECK_SLOTS.release()


async def _check_password(user: User | None, username: str, password: str) -> str | None:
    """Check `password` on a worker thread once a slot is free, refusing with 503 when none is.
    The attempt counts against `username` before the check starts, so concurrent guesses
    cannot pass the limit; an attempt refused for want of a slot does not count."""
    if not _PASSWORD_CHECK_SLOTS.acquire(blocking=False):
        logger.warning(
            "Sign-in refused: %s password checks already running", MAX_CONCURRENT_PASSWORD_CHECKS
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is busy. Try again in a moment.",
            headers={"Retry-After": "1"},
        )
    LOGIN_LIMIT.record(username)
    # Shielded, so a request cancelled while its check still waits for a thread does not
    # cancel the check, which alone gives the slot back.
    return await asyncio.shield(asyncio.to_thread(_login_failure_in_slot, user, password))


def _failure_detail(user: User | None, username: str, reason: str) -> dict[str, Any]:
    """A failed sign-in as the audit chain records it. The username is kept only when it names
    an account: an unknown one may be a password typed into the wrong box, and the chain is
    append-only."""
    detail: dict[str, Any] = {"success": False, "reason": reason}
    if user is not None:
        detail["username"] = username
    return detail


def _tokens_for(user_id: UUID) -> TokenResponse:
    subject = str(user_id)
    return TokenResponse(
        access_token=create_access_token(subject),
        refresh_token=create_refresh_token(subject),
    )


def _refresh_claims(token: str) -> _RefreshClaims:
    decoded = decode_token(token)
    if decoded is None or decoded.get("type") != "refresh":
        raise _RefreshRejectedError("invalid_token")
    try:
        user_id = UUID(str(decoded["sub"]))
    except ValueError as exc:
        raise _RefreshRejectedError("malformed_subject") from exc
    expires_at = datetime.fromtimestamp(int(decoded["exp"]), tz=UTC)
    return _RefreshClaims(user_id=user_id, jti=str(decoded["jti"]), expires_at=expires_at)


def _too_many(message: str, wait: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"{message} Try again in {wait} seconds.",
        headers={"Retry-After": str(wait)},
    )


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    username = payload.username.strip().lower()
    ip = client_ip(request)
    # Every attempt counts against its address before anything else is done for it.
    address_wait = LOGIN_ADDRESS_LIMIT.retry_after(ip or "unknown")
    if address_wait:
        logger.warning("Sign-in refused: too many attempts from %s", ip)
        raise _too_many("Too many sign-in attempts from this address.", address_wait)

    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    user_id = user.id if user else None
    # No await comes between this test and the count _check_password makes, so two attempts
    # cannot both pass the last place under the limit.
    wait = LOGIN_LIMIT.wait_time(username)
    if wait:
        detail = _failure_detail(user, username, "rate_limited")
        await _audit(db, AUDIT_LOGIN, user_id=user_id, ip=ip, detail=detail)
        raise _too_many("Too many failed sign-ins.", wait)

    reason = await _check_password(user, username, payload.password)
    if user is None or reason is not None:
        detail = _failure_detail(user, username, reason or "unknown_user")
        await _audit(db, AUDIT_LOGIN, user_id=user_id, ip=ip, detail=detail)
        raise _invalid_credentials()

    LOGIN_LIMIT.forget(username)
    detail = {"success": True, "username": username}
    await _audit(db, AUDIT_LOGIN, user_id=user.id, ip=ip, detail=detail)
    return _tokens_for(user.id)


@router.post("/refresh")
async def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> TokenResponse:
    ip = client_ip(request)
    try:
        claims = _refresh_claims(payload.refresh_token)
        if await is_revoked(db, claims.jti):
            raise _RefreshRejectedError("revoked_token")
    except _RefreshRejectedError as exc:
        detail = {"success": False, "reason": exc.reason}
        await _audit(db, AUDIT_REFRESH, user_id=None, ip=ip, detail=detail)
        raise _invalid_refresh() from exc

    user = (await db.execute(select(User).where(User.id == claims.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        detail = {"success": False, "reason": "inactive_user"}
        await _audit(db, AUDIT_REFRESH, user_id=user.id if user else None, ip=ip, detail=detail)
        raise _invalid_refresh()

    await revoke(db, jti=claims.jti, user_id=claims.user_id, expires_at=claims.expires_at)
    await _audit(db, AUDIT_REFRESH, user_id=user.id, ip=ip, detail={"success": True})
    return _tokens_for(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, request: Request, db: DbSession) -> None:
    ip = client_ip(request)
    try:
        claims = _refresh_claims(payload.refresh_token)
    except _RefreshRejectedError as exc:
        detail = {"success": False, "reason": exc.reason}
        await _audit(db, AUDIT_LOGOUT, user_id=None, ip=ip, detail=detail)
        raise _invalid_refresh() from exc

    if await is_revoked(db, claims.jti):
        detail = {"success": False, "reason": "already_revoked"}
        await _audit(db, AUDIT_LOGOUT, user_id=claims.user_id, ip=ip, detail=detail)
        raise _invalid_refresh()

    await revoke(db, jti=claims.jti, user_id=claims.user_id, expires_at=claims.expires_at)
    await _audit(db, AUDIT_LOGOUT, user_id=claims.user_id, ip=ip, detail={"success": True})


# A plain function: it awaits nothing (SonarQube python:S7503).
@router.get("/me")
def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
