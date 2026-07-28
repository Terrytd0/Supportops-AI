"""Password hashing, backed by passlib's bcrypt implementation.

The only place `users.password_hash` (docs/database_schema.md) should be
produced or checked — nothing else in the codebase should import `passlib`
directly.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash `plain_password` for storage in `users.password_hash`."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check `plain_password` against a previously stored hash."""
    return _pwd_context.verify(plain_password, password_hash)
