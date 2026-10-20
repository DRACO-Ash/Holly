"""The Users page's routes, for admins only: list the accounts, create one, reset a password, and
change a role or an account's status (ADR-014).

An admin sets a new account's first password, and any reset one, as a temporary password: the
account must choose its own before Holly lets it do anything else (app/dependencies.py). A reset
or a deactivation raises the account's token version, ending every session it holds. An admin
cannot reset, demote or deactivate their own account here, and the last active admin cannot be
demoted or deactivated, so Holly always keeps one. Each change reads the account again under a
lock before deciding (services/accounts.py), so no change made meanwhile is undone. Every change
is written to the audit chain.
"""

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.net import client_ip
from app.core.rate_limit import LOGIN_LIMIT
from app.core.security import hash_password
from app.dependencies import DbSession, require_role
from app.models.user import User, UserRole
from app.schemas.auth import UserRead
from app.schemas.users import PasswordReset, UserCreate, UserUpdate
from app.services.accounts import lock_users
from app.services.audit import write_audit

router = APIRouter(prefix="/users", tags=["users"])

Admin = Annotated[User, Depends(require_role(UserRole.ADMIN))]

AUDIT_CREATE = "auth.user.create"
AUDIT_RESET = "auth.user.password_reset"
AUDIT_UPDATE = "auth.user.update"


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def _in_use() -> HTTPException:
    return _conflict("That username or email is already in use.")


async def _audited(
    db: AsyncSession,
    request: Request,
    admin: User,
    action_type: str,
    target: User,
    detail: dict[str, Any],
) -> UserRead:
    await write_audit(
        db,
        action_type=action_type,
        entity_type="user",
        entity_id=str(target.id),
        user_id=admin.id,
        ip_address=client_ip(request),
        detail={"username": target.username, **detail},
    )
    await db.commit()
    await db.refresh(target)
    return UserRead.model_validate(target)


def _not_self(user_id: UUID, admin: User, action: str) -> None:
    if user_id == admin.id:
        raise _conflict(f"You cannot {action} your own account here.")


async def _locked_target(
    db: AsyncSession, user_id: UUID, *also: ColumnElement[bool]
) -> tuple[User, list[User]]:
    """The account to change, locked and read afresh, with every row `also` names, locked in
    the same statement."""
    rows = await lock_users(db, User.id == user_id, *also)
    user = next((row for row in rows if row.id == user_id), None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user, rows


def _keep_an_admin(user: User, role: str, active: bool, rows: list[User]) -> None:
    """Refuse a change that would take away the last active admin, counted among the locked
    rows as the locked read found them."""
    stays_admin = role == UserRole.ADMIN.value and active
    if user.role == UserRole.ADMIN.value and user.is_active and not stays_admin:
        admins = [row for row in rows if row.role == UserRole.ADMIN.value and row.is_active]
        if len(admins) <= 1:
            raise _conflict("Holly needs at least one active admin.")


@router.get("")
async def list_users(db: DbSession, _admin: Admin) -> list[UserRead]:
    users = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return [UserRead.model_validate(user) for user in users]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate, request: Request, db: DbSession, admin: Admin
) -> UserRead:
    clash = User.username == payload.username
    if payload.email is not None:
        # In any case: Bob@example.org and bob@example.org reach one inbox.
        clash = or_(clash, func.lower(User.email) == payload.email.lower())
    if (await db.execute(select(User.id).where(clash).limit(1))).scalar_one_or_none() is not None:
        raise _in_use()
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=await asyncio.to_thread(hash_password, payload.temporary_password),
        role=payload.role.value,
        is_active=True,
        must_change_password=True,
        token_version=0,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # Another request took the name or email between the check and the insert.
        await db.rollback()
        raise _in_use() from None
    return await _audited(db, request, admin, AUDIT_CREATE, user, {"role": user.role})


@router.post("/{user_id}/password")
async def reset_password(
    user_id: UUID, payload: PasswordReset, request: Request, db: DbSession, admin: Admin
) -> UserRead:
    _not_self(user_id, admin, "reset the password of")
    new_hash = await asyncio.to_thread(hash_password, payload.temporary_password)
    user, _ = await _locked_target(db, user_id)
    user.password_hash = new_hash
    user.must_change_password = True
    user.token_version += 1
    # A user locked out by failed sign-ins can try the new password at once.
    LOGIN_LIMIT.forget(user.username)
    return await _audited(db, request, admin, AUDIT_RESET, user, {})


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID, payload: UserUpdate, request: Request, db: DbSession, admin: Admin
) -> UserRead:
    _not_self(user_id, admin, "change the role or status of")
    # The account and every active admin, locked together, so two admins changing each other at
    # once cannot leave none.
    active_admin = and_(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
    user, rows = await _locked_target(db, user_id, active_admin)
    role = payload.role.value if payload.role is not None else user.role
    active = payload.is_active if payload.is_active is not None else user.is_active
    _keep_an_admin(user, role, active, rows)
    changes: dict[str, Any] = {}
    if role != user.role:
        changes["role"] = {"from": user.role, "to": role}
        user.role = role
    if active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": active}
        user.is_active = active
        if not active:
            # Ends every session now, and none returns if the account is activated again.
            user.token_version += 1
    if not changes:
        return UserRead.model_validate(user)
    return await _audited(db, request, admin, AUDIT_UPDATE, user, changes)
