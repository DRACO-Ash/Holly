"""Request dependencies: the database session and the signed-in user."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]

# The header that carries Holly's access token, the token alone (ADR-013). Not Authorization: the
# App Store's gateway refused Holly's token there with a 401 of its own, checking it against the
# platform's keys (20 October 2026), and reads any bearer token there as the platform's (inference).
# Holly never reads Authorization, so whatever the gateway puts there changes nothing.
# A header's name, not a secret.
TOKEN_HEADER = "X-Holly-Token"  # noqa: S105


def _credentials_error() -> HTTPException:
    """A new exception for each refusal: raising one shared instance again would add every
    request's frames to its traceback and keep them alive for the life of the process. The
    bare Bearer challenge stays, though the token travels in TOKEN_HEADER: it is how an operator
    tells Holly's 401 from the gateway's (operator manual, section 10)."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _access_subject(token: str | None) -> UUID:
    # The HTTP server trims the header's surrounding spaces; decode_token refuses anything else
    # that is not one of Holly's tokens.
    payload = decode_token(token) if token else None
    if payload is None or payload.get("type") != "access":
        raise _credentials_error()
    try:
        return UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise _credentials_error() from exc


async def get_current_user(
    db: DbSession, token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None
) -> User:
    user_id = _access_subject(token)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    allowed = {role.value for role in allowed_roles}

    # A plain function: it awaits nothing (SonarQube python:S7503).
    def checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges for this action",
            )
        return current_user

    return checker
