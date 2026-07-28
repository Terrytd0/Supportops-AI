"""Pydantic schemas for authentication request/response bodies.

Separate from a general `User` resource schema (not yet implemented) since
these shapes are specific to the auth flow: the bearer-token envelope and
the public projection of the current user.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from backend.database.enums import UserRole


class Token(BaseModel):
    """Response body for a successful `POST /auth/login`."""

    access_token: str
    token_type: str = "bearer"


class AuthenticatedUser(BaseModel):
    """Public projection of the current user, returned by `GET /auth/me`.

    Deliberately excludes `password_hash` — ORM models must never be
    returned directly from API routes (see CLAUDE.md, backend/schemas/README.md).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
