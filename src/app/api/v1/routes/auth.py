"""Sign-in, token refresh and sign-out, each written to the audit chain.

Failed sign-ins are limited per username (core/rate_limit.py); a success clears the count.
Every attempt costs one bcrypt check, against a dummy hash for an unknown username, so the
response time does not reveal which usernames exist. Refresh tokens rotate: each one works
once, and its id joins the block-list when it is used or signed out (ADR-011).
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.net import client_ip
from app.core.rate_limit import LOGIN_LIMIT
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

router = APIRouter(prefix="/auth", tags=["auth"])

_invalid_credentials = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid username or password",
)

_invalid_refresh = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid refresh token",
)


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


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenResponse:
    username = payload.username.strip().lower()
    ip = client_ip(request)
    wait = LOGIN_LIMIT.wait_time(username)
    if wait:
        detail = {"success": False, "username": username, "reason": "rate_limited"}
        await _audit(db, "auth.user.login", user_id=None, ip=ip, detail=detail)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed sign-ins. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )

    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    reason = _login_failure(user, payload.password)
    if user is None or reason is not None:
        LOGIN_LIMIT.record(username)
        detail = {"success": False, "username": username, "reason": reason}
        await _audit(db, "auth.user.login", user_id=user.id if user else None, ip=ip, detail=detail)
        raise _invalid_credentials

    LOGIN_LIMIT.forget(username)
    detail = {"success": True, "username": username}
    await _audit(db, "auth.user.login", user_id=user.id, ip=ip, detail=detail)
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
        await _audit(db, "auth.token.refresh", user_id=None, ip=ip, detail=detail)
        raise _invalid_refresh from exc

    user = (await db.execute(select(User).where(User.id == claims.user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        detail = {"success": False, "reason": "inactive_user"}
        await _audit(
            db, "auth.token.refresh", user_id=user.id if user else None, ip=ip, detail=detail
        )
        raise _invalid_refresh

    await revoke(db, jti=claims.jti, user_id=claims.user_id, expires_at=claims.expires_at)
    await _audit(db, "auth.token.refresh", user_id=user.id, ip=ip, detail={"success": True})
    return _tokens_for(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, request: Request, db: DbSession) -> None:
    ip = client_ip(request)
    try:
        claims = _refresh_claims(payload.refresh_token)
    except _RefreshRejectedError as exc:
        detail = {"success": False, "reason": exc.reason}
        await _audit(db, "auth.user.logout", user_id=None, ip=ip, detail=detail)
        raise _invalid_refresh from exc

    if await is_revoked(db, claims.jti):
        detail = {"success": False, "reason": "already_revoked"}
        await _audit(db, "auth.user.logout", user_id=claims.user_id, ip=ip, detail=detail)
        raise _invalid_refresh

    await revoke(db, jti=claims.jti, user_id=claims.user_id, expires_at=claims.expires_at)
    await _audit(db, "auth.user.logout", user_id=claims.user_id, ip=ip, detail={"success": True})


# A plain function: it awaits nothing (SonarQube python:S7503).
@router.get("/me")
def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
