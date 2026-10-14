"""Password hashing and JSON Web Tokens (JWT).

Tokens are signed with APP_SECRET_KEY using the configured HMAC algorithm (HS256 by default),
and decoding accepts only that one algorithm, so an unsigned or differently signed token never
verifies. PyJWT replaces the dashboard's python-jose; the claims are unchanged.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.config import get_settings

# bcrypt only considers the first 72 bytes of a password, and bcrypt 4.1 and later raise on
# longer input. Truncating at that boundary keeps the behaviour of earlier bcrypt releases:
# a password longer than 72 UTF-8 bytes is hashed and verified on its first 72 bytes.
_BCRYPT_MAX_BYTES = 72

TokenType = Literal["access", "refresh"]


def _to_bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: TokenType, lifetime: timedelta) -> str:
    settings = get_settings()
    payload = {
        "sub": subject,
        "exp": datetime.now(UTC) + lifetime,
        "type": token_type,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload, settings.app_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    lifetime = expires_delta or timedelta(minutes=get_settings().jwt_access_token_expire_minutes)
    return _create_token(subject, "access", lifetime)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    lifetime = expires_delta or timedelta(days=get_settings().jwt_refresh_token_expire_days)
    return _create_token(subject, "refresh", lifetime)


def decode_token(token: str) -> dict[str, Any] | None:
    """The token's claims when its signature and expiry verify, otherwise None."""
    settings = get_settings()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.app_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type", "jti"]},
        )
    except jwt.PyJWTError:
        return None
    return claims
