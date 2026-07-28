"""Framework-level security primitives shared across the API.

Deliberately free of auth-domain logic (password hashing, JWT claims, user
lookup) — that lives in `backend/auth/`. What belongs here is wiring any
FastAPI router could plausibly need without importing the auth package's
internals: the OAuth2 scheme and the standard 401/403 responses.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# tokenUrl must match the path backend/auth/router.py registers for login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

forbidden_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Not enough permissions",
)
