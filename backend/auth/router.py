"""Authentication routes: OAuth2 password login and the current-user endpoint.

Scope note: same as `auth/dependencies.py` — queries the database directly
via `async_session_factory` rather than a repository/service, since that
layer doesn't exist yet.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from backend.auth.dependencies import get_current_active_user
from backend.auth.hashing import hash_password, verify_password
from backend.auth.jwt import create_access_token
from backend.core.logging import get_logger
from backend.core.rate_limit import limiter
from backend.database.models.user import User
from backend.database.session import async_session_factory
from backend.schemas.auth import AuthenticatedUser, Token

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Tight limit on login specifically: it's the endpoint a credential-stuffing
# or brute-force attempt would hammer. Kept as a constant here, next to the
# route it guards, so it's easy to find and retune.
_LOGIN_RATE_LIMIT = "5/minute"

# Hashed once at import time and checked against on a not-found user, so a
# login attempt takes roughly the same time whether or not the email
# exists — avoids leaking account existence via response timing.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")


@router.post("/login", response_model=Token)
@limiter.limit(_LOGIN_RATE_LIMIT)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """OAuth2 password grant. `form_data.username` carries the user's email."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == form_data.username))
        user = result.scalar_one_or_none()

    if user is None:
        verify_password(form_data.password, _DUMMY_PASSWORD_HASH)
        logger.info("Authentication failed for %s: no such user", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.password_hash):
        logger.info("Authentication failed for %s: incorrect password", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.info("Authentication rejected for %s: inactive user", form_data.username)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    access_token = create_access_token(user_id=user.id, role=user.role)
    logger.info("Authentication succeeded for %s", form_data.username)
    return Token(access_token=access_token)


@router.get("/me", response_model=AuthenticatedUser)
async def read_current_user(user: User = Depends(get_current_active_user)) -> User:
    return user
