import enum

from sqlalchemy import Boolean, Integer, String, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(enum.StrEnum):
    ANALYST = "analyst"
    OPERATOR = "operator"
    ADMIN = "admin"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "app_user"

    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.ANALYST.value)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Set when an admin creates the account or resets its password: until the user chooses their
    # own, every route but /auth/me and /auth/password answers 403 (app/dependencies.py).
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # Every token carries the version it was issued under; raising it on a password change, a
    # reset or a deactivation refuses every token issued before (ADR-014).
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
