"""ORM model for supervisor approval requests on ticket responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, UUIDPrimaryKeyMixin
from backend.database.enums import ApprovalStatus, pg_enum

if TYPE_CHECKING:
    from backend.database.models.ticket import Ticket
    from backend.database.models.user import User


class ApprovalRequest(UUIDPrimaryKeyMixin, Base):
    """A supervisor approval gate a ticket response must pass before sending.

    docs/database_schema.md, "approval_requests" table. Tracks who
    requested approval, who ultimately decided it, and when each happened.
    Two foreign keys to `users` (`requested_by`, `approved_by`) require
    `foreign_keys=` on both this model's and `User`'s relationships to
    disambiguate the join.
    """

    __tablename__ = "approval_requests"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # Nullable: not yet decided while status == PENDING, mirroring the
    # explicitly-nullable `decided_at` column below.
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        pg_enum(ApprovalStatus, "approval_status"), nullable=False, index=True
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)

    ticket: Mapped[Ticket] = relationship(back_populates="approval_requests")
    requester: Mapped[User] = relationship(
        back_populates="requested_approvals", foreign_keys=[requested_by]
    )
    approver: Mapped[User | None] = relationship(
        back_populates="decided_approvals", foreign_keys=[approved_by]
    )
