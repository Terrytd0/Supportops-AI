"""ORM model for platform users (agents, supervisors, admins)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, CreatedAtUpdatedAtMixin, UUIDPrimaryKeyMixin
from backend.database.enums import UserRole, pg_enum

if TYPE_CHECKING:
    from backend.database.models.approval_request import ApprovalRequest
    from backend.database.models.audit_log import AuditLog
    from backend.database.models.ticket import Ticket


class User(UUIDPrimaryKeyMixin, CreatedAtUpdatedAtMixin, Base):
    """An authenticated platform user: an agent, supervisor, or admin.

    docs/database_schema.md, "users" table. Users are never hard-deleted —
    the schema's "Cascade Rules" disable user deletion entirely in favor of
    setting `is_active = false`, so that assigned tickets, approvals, and
    audit entries always retain a valid reference to who acted.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    assigned_tickets: Mapped[list[Ticket]] = relationship(back_populates="assigned_agent")
    requested_approvals: Mapped[list[ApprovalRequest]] = relationship(
        back_populates="requester", foreign_keys="ApprovalRequest.requested_by"
    )
    decided_approvals: Mapped[list[ApprovalRequest]] = relationship(
        back_populates="approver", foreign_keys="ApprovalRequest.approved_by"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
