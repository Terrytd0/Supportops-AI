"""ORM model for support tickets, the platform's primary business object."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, CreatedAtUpdatedAtMixin, UUIDPrimaryKeyMixin
from backend.database.enums import TicketPriority, TicketStatus, pg_enum

if TYPE_CHECKING:
    from backend.database.models.agent_run import AgentRun
    from backend.database.models.approval_request import ApprovalRequest
    from backend.database.models.audit_log import AuditLog
    from backend.database.models.customer import Customer
    from backend.database.models.user import User


class Ticket(UUIDPrimaryKeyMixin, CreatedAtUpdatedAtMixin, Base):
    """A customer support ticket — the platform's primary business object.

    docs/database_schema.md, "tickets" table. Every ticket belongs to
    exactly one customer, optionally has an assigned agent, and moves
    through the documented status flow (NEW -> ... -> CLOSED). It is the
    aggregation root for AI agent executions, approval requests, and audit
    history: none of those may cascade-delete when a ticket is removed.
    """

    __tablename__ = "tickets"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable: docs/database_schema.md does not mark this column NOT NULL,
    # and the documented "Status Flow" starts at NEW/TRIAGED, stages before
    # ASSIGNED — implying a ticket can exist before an agent is assigned.
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(
        pg_enum(TicketPriority, "ticket_priority"), nullable=False, index=True
    )
    status: Mapped[TicketStatus] = mapped_column(
        pg_enum(TicketStatus, "ticket_status"), nullable=False, index=True
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Overrides CreatedAtUpdatedAtMixin.created_at to add the `created_at`
    # index documented under "Indexes" for this table.
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )

    customer: Mapped["Customer"] = relationship(back_populates="tickets")
    assigned_agent: Mapped["User | None"] = relationship(back_populates="assigned_tickets")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="ticket")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="ticket")
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(back_populates="ticket")
