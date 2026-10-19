"""Create the first admin from the environment, once, at container start.

Whether the App Store offers a shell in the container for `python -m app.cli.create_admin` is
TBC, re-verify; this needs none. The gunicorn master calls run_admin_bootstrap after the
migrations (app/gunicorn_conf.py); `python -m app`, the development server, does not. When
ADMIN_USERNAME and ADMIN_PASSWORD are both set and Holly holds no account at all, it creates that
admin and records it in the audit chain. The accounts are counted before any value is checked,
and once any exists no value is checked or used: leaving them set, or removing ADMIN_PASSWORD
alone, can never reset a password, recreate a deleted admin or stop a start. Remove all three
from the platform after the first start all the same; the log names any still set.

While no account exists, half a pair, a password shorter than 12 characters, or a value Holly
cannot hash or store stops the container with a message naming the variable and never its value,
before the value reaches a query. The count and the insert run under an advisory lock, so two
containers starting at once create one admin between them.
"""

import asyncio
from collections.abc import Mapping

from sqlalchemy import func, select, text

from app.cli.create_admin import (
    MAX_EMAIL_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    unstorable_field,
)
from app.core.logging import log_event
from app.core.security import hash_password
from app.db.session import dispose_engine, get_session_factory
from app.models.user import User, UserRole
from app.services.audit import write_audit

# Distinct from the migrations' lock key, so neither waits on the other's.
ADMIN_BOOTSTRAP_LOCK_KEY = 0x484F4C41
ADMIN_VARIABLES = ("ADMIN_USERNAME", "ADMIN_PASSWORD", "ADMIN_EMAIL")
FIELD_PROBLEMS = {
    "password": "ADMIN_PASSWORD holds a character that is not valid UTF-8 text",
    "username": f"ADMIN_USERNAME must be 1 to {MAX_USERNAME_LENGTH} printable characters",
    "email": f"ADMIN_EMAIL must be at most {MAX_EMAIL_LENGTH} printable characters",
}


def _credentials(env: Mapping[str, str]) -> tuple[str, str, str | None]:
    """The admin to create, checked before any value reaches a query; a RuntimeError naming
    the variable, never its value, otherwise."""
    username = env.get("ADMIN_USERNAME", "").strip().lower()
    password = env.get("ADMIN_PASSWORD", "")
    # A password of spaces alone counts as unset, as it does when the bootstrap decides whether
    # it is configured at all.
    if not username or not password.strip():
        missing = "ADMIN_USERNAME" if not username else "ADMIN_PASSWORD"
        msg = f"{missing} is not set: set ADMIN_USERNAME and ADMIN_PASSWORD together, or neither"
        raise RuntimeError(msg)
    if len(password) < MIN_PASSWORD_LENGTH:
        msg = f"ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters"
        raise RuntimeError(msg)
    email = env.get("ADMIN_EMAIL", "").strip() or None
    field = unstorable_field(username, password, email)
    if field is not None:
        raise RuntimeError(FIELD_PROBLEMS[field])
    return username, password, email


async def bootstrap_admin(env: Mapping[str, str]) -> str:
    """Create the first admin when the environment names one and no account exists.

    Returns "not_configured", "accounts_exist" or "created", and logs the same with the names of
    any ADMIN_* variable still set. The accounts are counted before any value is checked, so
    once any exists no value is checked or used: removing ADMIN_PASSWORD alone, or leaving any of
    them set, never stops a start.
    """
    left_set = [name for name in ADMIN_VARIABLES if env.get(name, "").strip()]
    if not {"ADMIN_USERNAME", "ADMIN_PASSWORD"} & set(left_set):
        log_event("admin_bootstrap", status="not_configured", variables_still_set=left_set)
        return "not_configured"
    async with get_session_factory()() as session:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMIN_BOOTSTRAP_LOCK_KEY}
        )
        accounts = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        if accounts:
            await session.commit()
            # The names alone, so the log says what to remove from the platform.
            log_event("admin_bootstrap", status="accounts_exist", variables_still_set=left_set)
            return "accounts_exist"
        # No account yet: a half-set or unusable pair stops the start, and the lock's
        # transaction rolls back with nothing written.
        username, password, email = _credentials(env)
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        await write_audit(
            session,
            action_type="auth.user.admin_bootstrap",
            entity_type="user",
            entity_id=str(user.id),
            detail={"username": username},
        )
        await session.commit()
    log_event("admin_bootstrap", status="created", username=username)
    return "created"


async def _bootstrap_and_release(env: Mapping[str, str]) -> str:
    # The master forks the worker next: its pooled connections must not be inherited.
    try:
        return await bootstrap_admin(env)
    finally:
        await dispose_engine()


def run_admin_bootstrap(env: Mapping[str, str]) -> str:
    """The gunicorn master's entry point: run the bootstrap in its own event loop."""
    return asyncio.run(_bootstrap_and_release(env))
