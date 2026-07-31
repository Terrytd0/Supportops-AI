"""Repository for `ApprovalRequest` reads/writes -- the supervisor queue.

Owns every query `backend/api/supervisor.py` and `persist_results_node`
(`backend/graph/nodes.py`) need: creating a pending review item, listing/
fetching one, and recording a supervisor's decision. Every read eager-loads
`ticket` (`selectinload`) so callers can read `customer_id`/`priority` off
the related `Ticket` without a second query or an async lazy-load error.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.enums import ApprovalStatus
from backend.database.models.approval_request import ApprovalRequest


class ApprovalRequestRepository:
    """Read/write repository for the `approval_requests` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(
        self,
        *,
        ticket_id: uuid.UUID,
        draft_response: str,
        retrieved_context: str | None,
        selected_agent: str,
        matched_policy_rules: list[str],
    ) -> ApprovalRequest:
        """Enqueue a new supervisor review item for `ticket_id`.

        `requested_by` is left `None`: this is always called by
        `persist_results_node` when policy requires review, never by a
        human requesting review.
        """
        record = ApprovalRequest(
            ticket_id=ticket_id,
            status=ApprovalStatus.PENDING,
            draft_response=draft_response,
            retrieved_context=retrieved_context,
            selected_agent=selected_agent,
            matched_policy_rules=matched_policy_rules,
        )
        self._session.add(record)
        await self._session.flush()
        return await self._reload_with_ticket(record.id)

    async def list_pending(self) -> list[ApprovalRequest]:
        """Return every review item still awaiting a decision, oldest first."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING)
            .options(selectinload(ApprovalRequest.ticket))
            .order_by(ApprovalRequest.requested_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticket_id(self, ticket_id: uuid.UUID) -> ApprovalRequest | None:
        """Return `ticket_id`'s most recent review item, if any."""
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.ticket_id == ticket_id)
            .options(selectinload(ApprovalRequest.ticket))
            .order_by(ApprovalRequest.requested_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def decide(
        self,
        *,
        approval_request: ApprovalRequest,
        status: ApprovalStatus,
        reviewer_id: uuid.UUID,
        comments: str | None,
    ) -> ApprovalRequest:
        """Record a supervisor's approve/reject decision on `approval_request`."""
        approval_request.status = status
        approval_request.approved_by = reviewer_id
        approval_request.comments = comments
        approval_request.decided_at = datetime.now(UTC)
        await self._session.flush()
        return approval_request

    async def update_draft(
        self, *, approval_request: ApprovalRequest, draft_response: str
    ) -> ApprovalRequest:
        """Overwrite `approval_request`'s draft response (supervisor edit).

        Status is left as-is: editing is a distinct step *before* approval,
        not an implicit approve -- a supervisor still calls `/approve`
        afterward.
        """
        approval_request.draft_response = draft_response
        await self._session.flush()
        return approval_request

    async def _reload_with_ticket(self, approval_request_id: uuid.UUID) -> ApprovalRequest:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == approval_request_id)
            .options(selectinload(ApprovalRequest.ticket))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
