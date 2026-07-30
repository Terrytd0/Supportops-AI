"""Pydantic schemas for the supervisor approval-queue endpoints.

Boundary types for `backend/api/supervisor.py` — never expose the
`ApprovalRequest`/`Ticket` ORM models directly (see CLAUDE.md, "Schemas at
boundaries").
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.database.enums import ApprovalStatus, TicketPriority


class SupervisorQueueItem(BaseModel):
    """One ticket pending (or previously decided) supervisor approval.

    Field set mirrors `backend.database.models.approval_request.ApprovalRequest`
    joined with the ticket it belongs to.
    """

    model_config = ConfigDict(from_attributes=True)

    ticket_id: uuid.UUID
    customer_id: uuid.UUID
    priority: TicketPriority
    status: ApprovalStatus
    draft_response: str
    requested_at: datetime


class SupervisorQueueResponse(BaseModel):
    """Response body for `GET /supervisor/queue`."""

    items: list[SupervisorQueueItem]
    total: int


class ApprovalDecisionRequest(BaseModel):
    """Request body for `POST /supervisor/{ticket_id}/approve` and `/reject`."""

    comments: str | None = None


class ApprovalDecisionResponse(BaseModel):
    """Response body confirming an approve/reject decision."""

    ticket_id: uuid.UUID
    status: ApprovalStatus
    comments: str | None = None
    decided_at: datetime
