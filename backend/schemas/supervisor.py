"""Pydantic schemas for the supervisor approval-queue endpoints.

Boundary types for `backend/api/supervisor.py` — never expose the
`ApprovalRequest`/`Ticket` ORM models directly (see CLAUDE.md, "Schemas at
boundaries").
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from backend.database.enums import ApprovalStatus, TicketPriority


class SupervisorQueueItem(BaseModel):
    """One ticket pending (or previously decided) supervisor approval.

    Deliberately dashboard-ready: every field a supervisor dashboard needs
    to render a queue row -- ticket, assigned AI agent, matched policy
    rules, draft response, retrieved knowledge, queue status, and created
    time -- is present on this one shape, returned by every endpoint below
    (list, get, approve, edit, reject) so a client renders one component
    regardless of which action produced the response.
    """

    ticket_id: uuid.UUID
    customer_id: uuid.UUID
    priority: TicketPriority
    status: ApprovalStatus
    selected_agent: str
    matched_policy_rules: list[str]
    draft_response: str
    retrieved_context: str | None = None
    comments: str | None = None
    requested_at: datetime
    reviewed_at: datetime | None = None
    reviewer_id: uuid.UUID | None = None


class SupervisorQueueResponse(BaseModel):
    """Response body for `GET /supervisor/queue`."""

    items: list[SupervisorQueueItem]
    total: int


class ApprovalDecisionRequest(BaseModel):
    """Request body for `POST /supervisor/queue/{ticket_id}/approve` and `/reject`."""

    comments: str | None = None


class EditDraftRequest(BaseModel):
    """Request body for `POST /supervisor/queue/{ticket_id}/edit`.

    Edits the draft in place; status is left untouched (still `PENDING`) --
    the supervisor still calls `/approve` afterward to finalize it.
    """

    draft_response: str
