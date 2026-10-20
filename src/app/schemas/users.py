"""What the Users page sends (routes/users.py): an account to create, a temporary password, and
a change of role or status. Each value is checked before any query, as the first admin's are."""

import re
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, BeforeValidator, model_validator

from app.cli.create_admin import MAX_EMAIL_LENGTH, MAX_USERNAME_LENGTH
from app.db.storable import storable_text
from app.models.user import UserRole
from app.schemas.auth import NewPassword


def _stripped(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _printable(limit: int) -> AfterValidator:
    def check(value: str) -> str:
        if not (0 < len(value) <= limit and storable_text(value) and value.isprintable()):
            msg = f"must be 1 to {limit} printable characters"
            raise ValueError(msg)
        return value

    return AfterValidator(check)


def _stripped_lower(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


# Letters a to z, digits and . _ @ -, so no new name can pass for another on the Users page or in
# the audit view: a Cyrillic a (U+0430) for a Latin one, or a letter with a combining accent.
_PLAIN_USERNAME = re.compile(r"[a-z0-9._@-]+")


def _plain_username(value: str) -> str:
    if not (len(value) <= MAX_USERNAME_LENGTH and _PLAIN_USERNAME.fullmatch(value)):
        msg = f"use 1 to {MAX_USERNAME_LENGTH} of a to z, 0 to 9 and . _ @ -"
        raise ValueError(msg)
    return value


# Trimmed and lowercased, as every sign-in reads it.
Username = Annotated[str, BeforeValidator(_stripped_lower), AfterValidator(_plain_username)]
# Trimmed; empty means none.
Email = Annotated[str, BeforeValidator(_stripped), _printable(MAX_EMAIL_LENGTH)]


class UserCreate(BaseModel):
    username: Username
    email: Email | None = None
    role: UserRole = UserRole.ANALYST
    temporary_password: NewPassword

    @model_validator(mode="before")
    @classmethod
    def _empty_email_is_none(cls, data: object) -> object:
        if isinstance(data, dict):
            email = data.get("email")
            if isinstance(email, str) and not email.strip():
                return {**data, "email": None}
        return data


class PasswordReset(BaseModel):
    temporary_password: NewPassword


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if self.role is None and self.is_active is None:
            msg = "name a role or a status to change"
            raise ValueError(msg)
        return self
