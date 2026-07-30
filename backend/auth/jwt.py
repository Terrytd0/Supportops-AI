"""JWT access-token creation and verification.

Encoding/decoding only — password verification (`auth/hashing.py`) and user
lookup (`auth/dependencies.py`) are deliberately kept out of this module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import jwt as jose_jwt
from pydantic import BaseModel

from backend.config.settings import get_settings
from backend.database.enums import UserRole

settings = get_settings()


class TokenPayload(BaseModel):
    """Validated claims of a decoded access token."""

    sub: str
    role: UserRole
    exp: datetime


def create_access_token(
    user_id: uuid.UUID,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    """Issue a signed JWT access token for `user_id`.

    `expires_delta` overrides `settings.jwt_access_token_expire_minutes`;
    exposed mainly so callers (tests, refresh-token logic) aren't tied to
    wall-clock timing.
    """
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    claims = {"sub": str(user_id), "role": role.value, "exp": expire}
    return jose_jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate `token`.

    Raises `jose.JWTError` (bad signature, malformed token, expired `exp`,
    ...) on failure; callers translate that into an HTTP response — see
    `auth/dependencies.py:get_current_user`.
    """
    payload = jose_jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return TokenPayload(**payload)
