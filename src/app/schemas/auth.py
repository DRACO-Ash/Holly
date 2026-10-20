from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.cli.create_admin import MIN_PASSWORD_LENGTH
from app.models.user import UserRole
from app.schemas.common import StorableText

# Bounds on what a caller may send. bcrypt reads only the first 72 bytes of a password and a
# Holly token is a few hundred characters, so anything longer is refused before any work.
MAX_PASSWORD_LENGTH = 1024
MAX_TOKEN_LENGTH = 4096


class LoginRequest(BaseModel):
    username: StorableText = Field(..., min_length=1, max_length=50)
    password: StorableText = Field(..., min_length=1, max_length=MAX_PASSWORD_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    # The OAuth 2 token type, not a secret.
    token_type: str = "bearer"  # noqa: S105


def _not_blank(value: str) -> str:
    if not value.strip():
        msg = "must not be spaces alone"
        raise ValueError(msg)
    return value


# A password Holly sets: at least 12 characters, as for the first admin, and not spaces alone.
NewPassword = Annotated[
    StorableText,
    Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH),
    AfterValidator(_not_blank),
]


class PasswordChangeRequest(BaseModel):
    current_password: StorableText = Field(..., min_length=1, max_length=MAX_PASSWORD_LENGTH)
    new_password: NewPassword


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=MAX_TOKEN_LENGTH)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=MAX_TOKEN_LENGTH)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None = None
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime
