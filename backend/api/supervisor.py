"""Supervisor approval-queue endpoints: list, inspect, approve, edit, reject.

The real supervisor queue: `ApprovalRequest` rows
(`backend.database.models.approval_request`), not an in-memory placeholder.
A row is created by `backend.graph.nodes.persist_results_node` whenever
policy (`backend.policy.rules.evaluate_policy`) sets
`requires_human_review=True` -- policy remains the only component that
decides a ticket enters this queue; CrewAI agents never enqueue tickets, and
LangGraph never makes that business decision itself.

Every route requires the `supervisor` or `admin` role
(`backend.auth.dependencies.require_role`) and audit-logs the action it
performed (`backend.services.audit.log_audit_event`).

Scope note: queries the database directly via `async_session_factory`
rather than a repository-consuming service, since that layer doesn't exist
yet -- same as `backend/auth/router.py`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.auth.dependencies import require_role
from backend.core.logging import get_logger
from backend.core.rate_limit import limiter
from backend.database.enums import ApprovalStatus, UserRole
from backend.database.models.approval_request import ApprovalRequest
from backend.database.models.user import User
from backend.database.repositories.approval_request import ApprovalRequestRepository
from backend.database.session import async_session_factory
from backend.schemas.supervisor import (
    ApprovalDecisionRequest,
    EditDraftRequest,
    SupervisorQueueItem,
    SupervisorQueueResponse,
)
from backend.services.audit import log_audit_event

logger = get_logger(__name__)

router = APIRouter(prefix="/supervisor", tags=["supervisor"])

# Looser than login: supervisors working the queue may approve/reject in
# quick succession, but this still bounds abuse/runaway-client traffic.
_APPROVAL_DECISION_RATE_LIMIT = "30/minute"

# Both roles may work the queue (docs/database_schema.md, "User Roles":
# Supervisor's capabilities are a superset of Agent's, and Admin's a
# superset of Supervisor's).
_SUPERVISOR_ROLES = (UserRole.SUPERVISOR, UserRole.ADMIN)


def _to_queue_item(approval_request: ApprovalRequest) -> SupervisorQueueItem:
    """Build the dashboard-ready response shape from an `ApprovalRequest`.

    Reads `customer_id`/`priority` off `approval_request.ticket` (must
    already be eager-loaded -- see `ApprovalRequestRepository`) rather than
    duplicating those columns on `ApprovalRequest` itself.
    """
    ticket = approval_request.ticket
    return SupervisorQueueItem(
        ticket_id=approval_request.ticket_id,
        customer_id=ticket.customer_id,
        priority=ticket.priority,
        status=approval_request.status,
        selected_agent=approval_request.selected_agent,
        matched_policy_rules=list(approval_request.matched_policy_rules),
        draft_response=approval_request.draft_response,
        retrieved_context=approval_request.retrieved_context,
        comments=approval_request.comments,
        requested_at=approval_request.requested_at,
        reviewed_at=approval_request.decided_at,
        reviewer_id=approval_request.approved_by,
    )


async def _get_or_404(
    repository: ApprovalRequestRepository, ticket_id: uuid.UUID
) -> ApprovalRequest:
    approval_request = await repository.get_by_ticket_id(ticket_id)
    if approval_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found in supervisor queue",
        )
    return approval_request


@router.get("/queue", response_model=SupervisorQueueResponse)
async def list_queue(
    user: User = Depends(require_role(*_SUPERVISOR_ROLES)),
) -> SupervisorQueueResponse:
    """List every ticket pending supervisor approval."""
    async with async_session_factory() as session:
        repository = ApprovalRequestRepository(session)
        pending = await repository.list_pending()
        items = [_to_queue_item(item) for item in pending]
    return SupervisorQueueResponse(items=items, total=len(items))


@router.get("/queue/{ticket_id}", response_model=SupervisorQueueItem)
async def get_queue_item(
    ticket_id: uuid.UUID,
    user: User = Depends(require_role(*_SUPERVISOR_ROLES)),
) -> SupervisorQueueItem:
    """Fetch a single ticket's supervisor-queue entry."""
    async with async_session_factory() as session:
        repository = ApprovalRequestRepository(session)
        approval_request = await _get_or_404(repository, ticket_id)
        item = _to_queue_item(approval_request)
    await log_audit_event(
        ticket_id=ticket_id,
        event_type="supervisor_viewed",
        description="Supervisor viewed the AI draft response.",
        user_id=user.id,
    )
    return item


@router.post("/queue/{ticket_id}/approve", response_model=SupervisorQueueItem)
@limiter.limit(_APPROVAL_DECISION_RATE_LIMIT)
async def approve_ticket(
    request: Request,
    ticket_id: uuid.UUID,
    decision: ApprovalDecisionRequest,
    user: User = Depends(require_role(*_SUPERVISOR_ROLES)),
) -> SupervisorQueueItem:
    """Approve a ticket's draft response for sending."""
    async with async_session_factory() as session:
        repository = ApprovalRequestRepository(session)
        approval_request = await _get_or_404(repository, ticket_id)
        approval_request = await repository.decide(
            approval_request=approval_request,
            status=ApprovalStatus.APPROVED,
            reviewer_id=user.id,
            comments=decision.comments,
        )
        await session.commit()
        item = _to_queue_item(approval_request)
    logger.info("Supervisor %s approved ticket %s", user.id, ticket_id)
    await log_audit_event(
        ticket_id=ticket_id,
        event_type="supervisor_approved",
        description="Supervisor approved the AI draft response.",
        user_id=user.id,
        metadata={"comments": decision.comments},
    )
    return item


@router.post("/queue/{ticket_id}/edit", response_model=SupervisorQueueItem)
@limiter.limit(_APPROVAL_DECISION_RATE_LIMIT)
async def edit_draft(
    request: Request,
    ticket_id: uuid.UUID,
    edit: EditDraftRequest,
    user: User = Depends(require_role(*_SUPERVISOR_ROLES)),
) -> SupervisorQueueItem:
    """Modify a ticket's AI draft response before approving it."""
    async with async_session_factory() as session:
        repository = ApprovalRequestRepository(session)
        approval_request = await _get_or_404(repository, ticket_id)
        approval_request = await repository.update_draft(
            approval_request=approval_request, draft_response=edit.draft_response
        )
        await session.commit()
        item = _to_queue_item(approval_request)
    logger.info("Supervisor %s edited ticket %s's draft response", user.id, ticket_id)
    await log_audit_event(
        ticket_id=ticket_id,
        event_type="supervisor_edited",
        description="Supervisor edited the AI draft response.",
        user_id=user.id,
    )
    return item


@router.post("/queue/{ticket_id}/reject", response_model=SupervisorQueueItem)
@limiter.limit(_APPROVAL_DECISION_RATE_LIMIT)
async def reject_ticket(
    request: Request,
    ticket_id: uuid.UUID,
    decision: ApprovalDecisionRequest,
    user: User = Depends(require_role(*_SUPERVISOR_ROLES)),
) -> SupervisorQueueItem:
    """Reject a ticket's draft response and mark it for manual handling."""
    async with async_session_factory() as session:
        repository = ApprovalRequestRepository(session)
        approval_request = await _get_or_404(repository, ticket_id)
        approval_request = await repository.decide(
            approval_request=approval_request,
            status=ApprovalStatus.REJECTED,
            reviewer_id=user.id,
            comments=decision.comments,
        )
        await session.commit()
        item = _to_queue_item(approval_request)
    logger.info("Supervisor %s rejected ticket %s", user.id, ticket_id)
    await log_audit_event(
        ticket_id=ticket_id,
        event_type="supervisor_rejected",
        description="Supervisor rejected the AI draft response; marked for manual handling.",
        user_id=user.id,
        metadata={"comments": decision.comments},
    )
    return item
