"""Test doubles shared by the route and service tests: a database session that hands out
canned results in order and records writes, and builders for the rows routes read."""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from app.core.security import hash_password
from app.models.user import User, UserRole

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


class FakeSession:
    """A stand-in for an AsyncSession.

    `results` are handed out in order, one per `execute` call; each is shaped like a
    SQLAlchemy result (see scalar_result and rows_result), so a test states exactly the rows
    the code under test will see, and a call it did not expect fails loudly. Writes are
    recorded, not performed.
    """

    def __init__(self, results: list[Any] | None = None) -> None:
        self.execute = AsyncMock(side_effect=list(results or []))
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.refresh = AsyncMock()
        self.flush = AsyncMock()
        self.delete = AsyncMock()
        self.added: list[Any] = []

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    def add_all(self, instances: list[Any]) -> None:
        self.added.extend(instances)


def scalar_result(value: Any) -> MagicMock:
    """A result whose scalar_one_or_none(), scalar_one() and scalar() all return `value`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalar.return_value = value
    return result


def rows_result(rows: list[Any]) -> MagicMock:
    """A result whose scalars().all(), all() and iteration all give `rows`."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    result.scalars.return_value.first.return_value = rows[0] if rows else None
    result.all.return_value = rows
    result.__iter__.return_value = iter(rows)
    return result


def make_user(
    *,
    username: str = "alice",
    password: str | None = None,
    role: UserRole = UserRole.ANALYST,
    is_active: bool = True,
) -> User:
    """A user row as the database would return it. The password hash is computed only when a
    test signs in with a password, because bcrypt is deliberately slow."""
    return User(
        id=uuid.uuid4(),
        username=username,
        email=None,
        password_hash=hash_password(password) if password is not None else "unused",
        role=role.value,
        is_active=is_active,
        created_at=NOW,
        updated_at=NOW,
    )
