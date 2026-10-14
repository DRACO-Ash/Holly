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


def _credentials_error() -> HTTPException:
    """A new exception for each refusal: raising one shared instance again would add every
    request's frames to its traceback and keep them alive for the life of the process."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _credentials_error()
    return authorization.split(" ", 1)[1].strip()


def _access_subject(authorization: str | None) -> UUID:
    payload = decode_token(_extract_bearer_token(authorization))
    if payload is None or payload.get("type") != "access":
        raise _credentials_error()
    try:
        return UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise _credentials_error() from exc


async def get_current_user(
    db: DbSession, authorization: Annotated[str | None, Header()] = None
) -> User:
    user_id = _access_subject(authorization)
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
