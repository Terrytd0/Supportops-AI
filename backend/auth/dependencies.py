"""FastAPI dependencies for resolving and authorizing the current user.

Scope note: user lookup goes through `async_session_factory` directly
rather than a repository/service — that layer (backend/database/README.md
TODOs) doesn't exist yet. This module should be the only place that needs
to change once it does.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends
from jose import JWTError

from backend.auth.jwt import decode_access_token
from backend.core.security import credentials_exception, forbidden_exception, oauth2_scheme
from backend.database.enums import UserRole
from backend.database.models.user import User
from backend.database.session import async_session_factory


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Resolve the `User` identified by a bearer token's `sub` claim."""
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload.sub)
    except (JWTError, ValueError) as exc:
        raise credentials_exception from exc

    async with async_session_factory() as session:
        user = await session.get(User, user_id)

    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    """Reject deactivated accounts (`users.is_active = false`)."""
    if not user.is_active:
        raise forbidden_exception
    return user


def require_role(*allowed_roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency factory restricting a route to specific `UserRole`s.

    Usage: `Depends(require_role(UserRole.SUPERVISOR, UserRole.ADMIN))`.
    Only checks membership in `allowed_roles` — it does not encode the
    Agent/Supervisor/Admin capability hierarchy described in
    docs/database_schema.md; routes compose the exact role sets they need.
    """

    async def _check(user: User = Depends(get_current_active_user)) -> User:
        if user.role not in allowed_roles:
            raise forbidden_exception
        return user

    return _check
