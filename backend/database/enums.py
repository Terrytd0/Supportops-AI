"""Enum types shared across ORM models.

Every ENUM column documented in docs/database_schema.md is defined exactly
once here; models import from this module instead of redefining values, so
the set of valid values for e.g. ticket status has a single source of truth.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SQLEnum


class UserRole(str, enum.Enum):
    """`users.role` — docs/database_schema.md, "users" table."""

    AGENT = "agent"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class CustomerTier(str, enum.Enum):
    """`customers.tier` — docs/database_schema.md, "customers" table."""

    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class TicketPriority(str, enum.Enum):
    """`tickets.priority` — docs/database_schema.md, "tickets" table."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(str, enum.Enum):
    """`tickets.status` — docs/database_schema.md, "tickets" table and
    "Status Flow" (NEW -> TRIAGED -> ASSIGNED -> DRAFTED ->
    APPROVAL_REQUIRED -> APPROVED -> SENT -> CLOSED).
    """

    NEW = "new"
    TRIAGED = "triaged"
    ASSIGNED = "assigned"
    DRAFTED = "drafted"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    SENT = "sent"
    CLOSED = "closed"


class ApprovalStatus(str, enum.Enum):
    """`approval_requests.status` — docs/database_schema.md, "approval_requests" table."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def _member_values(enum_cls: type[enum.Enum]) -> list[str]:
    """`values_callable` for `pg_enum`: persist `.value`, not `.name`.

    SQLAlchemy's `Enum` type persists a member's *name* (e.g. "AGENT") by
    default, not its `.value`. Every enum above is written with uppercase
    Python member names but lowercase values matching the schema's
    documented ENUM values (e.g. "agent") exactly, so every enum column
    must be built through `pg_enum` rather than `SQLEnum(...)` directly.
    """
    return [member.value for member in enum_cls]


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SQLEnum:
    """Build a native PostgreSQL ENUM type bound to `enum_cls`.

    `name` becomes the Postgres type name (e.g. `CREATE TYPE user_role AS
    ENUM (...)`); centralizing construction here keeps that naming and the
    `values_callable` wiring consistent across every model.
    """
    return SQLEnum(enum_cls, name=name, values_callable=_member_values)
