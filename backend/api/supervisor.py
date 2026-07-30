"""Supervisor approval-queue endpoints: list, inspect, approve, reject.

Placeholder-only, per Sprint 4 Day 4 scope: every handler reads/writes an
in-memory placeholder queue instead of Postgres. Kept at `backend/api/`
(rather than `backend/api/routes/`) as the router for the supervisor
resource; register it in `backend/main.py`.

TODO(Repository): replace `_PLACEHOLDER_QUEUE` and `_find_placeholder_item`
with reads/writes via an `ApprovalRequestRepository` (see
`backend/database/repositories/`) against
`backend.database.models.approval_request.ApprovalRequest`, joined with
`backend.database.models.ticket.Ticket`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from backend.core.logging import get_logger
from backend.core.rate_limit import limiter
from backend.database.enums import ApprovalStatus, TicketPriority
from backend.schemas.supervisor import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    SupervisorQueueItem,
    SupervisorQueueResponse,
)
from backend.services.audit import log_audit_event

logger = get_logger(__name__)

router = APIRouter(prefix="/supervisor", tags=["supervisor"])

# Looser than login: supervisors working the queue may approve/reject in
# quick succession, but this still bounds abuse/runaway-client traffic.
# Kept as a constant here, next to the routes it guards, so it's easy to
# find and retune.
_APPROVAL_DECISION_RATE_LIMIT = "30/minute"

# Deterministic placeholder data standing in for a repository read against
# `approval_requests`/`tickets`. TODO(Repository): replace with
# ApprovalRequestRepository.list_pending(...).
_PLACEHOLDER_QUEUE: tuple[SupervisorQueueItem, ...] = (
    SupervisorQueueItem(
        ticket_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        customer_id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
        priority=TicketPriority.HIGH,
        status=ApprovalStatus.PENDING,
        draft_response="Placeholder response awaiting supervisor approval.",
        requested_at=datetime(2026, 1, 1, tzinfo=UTC),
    ),
)


def _find_placeholder_item(ticket_id: uuid.UUID) -> SupervisorQueueItem:
    """Look up a queue entry by ticket id, or raise 404.

    TODO(Repository): replace with ApprovalRequestRepository.get_by_ticket_id(...).
    """
    for item in _PLACEHOLDER_QUEUE:
        if item.ticket_id == ticket_id:
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Ticket not found in supervisor queue",
    )


@router.get("/queue", response_model=SupervisorQueueResponse)
async def list_queue() -> SupervisorQueueResponse:
    """List tickets pending supervisor approval.

    TODO(Repository): replace with a paginated
    ApprovalRequestRepository.list_pending(...) call.
    """
    return SupervisorQueueResponse(items=list(_PLACEHOLDER_QUEUE), total=len(_PLACEHOLDER_QUEUE))


@router.get("/queue/{ticket_id}", response_model=SupervisorQueueItem)
async def get_queue_item(ticket_id: uuid.UUID) -> SupervisorQueueItem:
    """Fetch a single ticket's supervisor-queue entry.

    TODO(Repository): replace with ApprovalRequestRepository.get_by_ticket_id(...).
    """
    return _find_placeholder_item(ticket_id)


@router.post("/{ticket_id}/approve", response_model=ApprovalDecisionResponse)
@limiter.limit(_APPROVAL_DECISION_RATE_LIMIT)
async def approve_ticket(
    request: Request, ticket_id: uuid.UUID, decision: ApprovalDecisionRequest
) -> ApprovalDecisionResponse:
    """Approve a ticket's draft response for sending.

    TODO(Repository): replace with ApprovalRequestRepository.decide(...)
    writing `ApprovalStatus.APPROVED` inside a transaction that also updates
    the ticket status.
    """
    _find_placeholder_item(ticket_id)
    logger.info("Supervisor approved ticket %s", ticket_id)
    log_audit_event(
        ticket_id=ticket_id,
        event_type="supervisor_approved",
        description="Supervisor approved ticket response.",
        metadata={"comments": decision.comments},
    )
    return ApprovalDecisionResponse(
        ticket_id=ticket_id,
        status=ApprovalStatus.APPROVED,
        comments=decision.comments,
        decided_at=datetime.now(UTC),
    )


@router.post("/{ticket_id}/reject", response_model=ApprovalDecisionResponse)
@limiter.limit(_APPROVAL_DECISION_RATE_LIMIT)
async def reject_ticket(
    request: Request, ticket_id: uuid.UUID, decision: ApprovalDecisionRequest
) -> ApprovalDecisionResponse:
    """Reject a ticket's draft response.

    TODO(Repository): replace with ApprovalRequestRepository.decide(...)
    writing `ApprovalStatus.REJECTED` inside a transaction that also updates
    the ticket status.
    """
    _find_placeholder_item(ticket_id)
    logger.info("Supervisor rejected ticket %s", ticket_id)
    log_audit_event(
        ticket_id=ticket_id,
        event_type="supervisor_rejected",
        description="Supervisor rejected ticket response.",
        metadata={"comments": decision.comments},
    )
    return ApprovalDecisionResponse(
        ticket_id=ticket_id,
        status=ApprovalStatus.REJECTED,
        comments=decision.comments,
        decided_at=datetime.now(UTC),
    )
