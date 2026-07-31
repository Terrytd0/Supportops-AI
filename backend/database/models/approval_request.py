"""ORM model for supervisor approval requests on ticket responses.

This is the supervisor queue's backing table: `requires_human_review=True`
(`backend.policy.rules.evaluate_policy`, via `persist_results_node`) creates
a row here; `backend/api/supervisor.py`'s queue endpoints read and decide
them. Deliberately not a separate "queue" table -- an approval request
*is* a supervisor queue item, and a second table would just duplicate it
(see `backend/api/supervisor.py`'s module docstring).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, UUIDPrimaryKeyMixin
from backend.database.enums import ApprovalStatus, pg_enum

if TYPE_CHECKING:
    from backend.database.models.ticket import Ticket
    from backend.database.models.user import User


class ApprovalRequest(UUIDPrimaryKeyMixin, Base):
    """A supervisor approval gate a ticket response must pass before sending.

    docs/database_schema.md, "approval_requests" table, extended with the
    AI-execution context (`draft_response`, `retrieved_context`,
    `selected_agent`, `matched_policy_rules`) a supervisor needs to review a
    ticket without a second join -- see docs/database_schema.md's history
    for why those weren't there originally. Two foreign keys to `users`
    (`requested_by`, `approved_by`) require `foreign_keys=` on both this
    model's and `User`'s relationships to disambiguate the join.

    `customer_id`/`priority` are deliberately *not* duplicated here: they
    already live on `Ticket` and are reached via the `ticket` relationship
    (see `backend.database.repositories.approval_request
    .ApprovalRequestRepository`, which eager-loads it).
    """

    __tablename__ = "approval_requests"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable: most rows are created automatically by persist_results_node
    # when policy requires review, not requested by a human user. NULL means
    # "system/AI-requested"; docs/database_schema.md originally documented
    # this as NOT NULL, back when only a human could request approval.
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
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
    # Timezone-aware, unlike every other timestamp column here: those are all
    # DB-side `server_default=func.now()` values, never touched from Python.
    # `decided_at` is the one column the application itself sets
    # (`ApprovalRequestRepository.decide`, with `datetime.now(UTC)`), so the
    # column must actually be able to hold a timezone-aware value.
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- AI execution context, snapshotted at creation time ---
    draft_response: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_agent: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_policy_rules: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    ticket: Mapped[Ticket] = relationship(back_populates="approval_requests")
    requester: Mapped[User | None] = relationship(
        back_populates="requested_approvals", foreign_keys=[requested_by]
    )
    approver: Mapped[User | None] = relationship(
        back_populates="decided_approvals", foreign_keys=[approved_by]
    )
