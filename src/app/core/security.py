"""Password hashing and JSON Web Tokens (JWT).

Tokens are signed with APP_SECRET_KEY using the configured HMAC algorithm (HS256 by default),
and decoding accepts only that one algorithm, so an unsigned or differently signed token never
verifies. PyJWT replaces the dashboard's python-jose. Since V0.10 each token also carries `ver`,
the user's token version when it was issued (ADR-014); a token without it, issued before, reads
as version 0.
"""

import hmac
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


def same_password(first: str, second: str) -> bool:
    """Whether bcrypt would read the two as one password, compared in constant time."""
    return hmac.compare_digest(_to_bcrypt_bytes(first), _to_bcrypt_bytes(second))


def _create_token(subject: str, token_type: TokenType, lifetime: timedelta, version: int) -> str:
    settings = get_settings()
    payload = {
        "sub": subject,
        "exp": datetime.now(UTC) + lifetime,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "ver": version,
    }
    return jwt.encode(
        payload, settings.app_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def create_access_token(
    subject: str, expires_delta: timedelta | None = None, *, version: int = 0
) -> str:
    lifetime = expires_delta or timedelta(minutes=get_settings().jwt_access_token_expire_minutes)
    return _create_token(subject, "access", lifetime, version)


def create_refresh_token(
    subject: str, expires_delta: timedelta | None = None, *, version: int = 0
) -> str:
    lifetime = expires_delta or timedelta(days=get_settings().jwt_refresh_token_expire_days)
    return _create_token(subject, "refresh", lifetime, version)


def token_version(claims: dict[str, Any]) -> int | None:
    """The token version a decoded token carries: 0 when it has none, None when it is not a
    whole number, which no user's version can equal."""
    version = claims.get("ver", 0)
    if isinstance(version, bool) or not isinstance(version, int):
        return None
    return version


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
