from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    token_type: str = "bearer"  # noqa: S105  the OAuth 2 token type, not a secret


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
    created_at: datetime
