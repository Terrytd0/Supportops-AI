"""ORM model for the immutable audit trail of business/system actions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.database.models.ticket import Ticket
    from backend.database.models.user import User


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """An immutable record of a single business or system action.

    docs/database_schema.md, "audit_logs" table. Rows are append-only
    (ticket created, AI response generated, supervisor approved, status
    changed, customer notified, ...) and form the platform's permanent
    audit history; per "Cascade Rules", nothing in this schema deletes a
    ticket's audit history.

    The documented `metadata` column is exposed as `event_metadata` on
    this model: `metadata` is reserved on SQLAlchemy's `DeclarativeBase`
    (it holds the class's table metadata), so the Python attribute is
    renamed while the underlying database column stays exactly
    `metadata`, via `mapped_column("metadata", ...)`.
    """

    __tablename__ = "audit_logs"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )

    ticket: Mapped[Ticket] = relationship(back_populates="audit_logs")
    user: Mapped[User | None] = relationship(back_populates="audit_logs")
