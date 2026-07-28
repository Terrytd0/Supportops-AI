"""Declarative base and reusable field mixins for SQLAlchemy ORM models.

Centralizing these here means every model in `backend/database/models/`
shares one `MetaData` (with one naming convention) and one implementation
of the "UUID primary key" / "created_at timestamp" patterns that recur
across nearly every table in docs/database_schema.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint/index names so Alembic autogenerate (next
# milestone) produces stable, readable migrations instead of dialect-default
# names like `tickets_customer_id_fkey1`.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base for every ORM model in this package."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Adds a UUID `id` primary key, generated application-side.

    docs/database_schema.md specifies `UUID | PK` for every table but does
    not say how the value is generated. `uuid.uuid4()` as a Python-side
    default is used rather than a server-side `gen_random_uuid()`/
    `uuid_generate_v4()` default so no Postgres extension is required for
    the ORM layer to function on its own — see the Deliverables notes.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class CreatedAtMixin:
    """Adds a NOT NULL `created_at` timestamp, stamped at insert time."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class CreatedAtUpdatedAtMixin(CreatedAtMixin):
    """Adds `created_at` plus a NOT NULL `updated_at`, refreshed on update."""

    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
