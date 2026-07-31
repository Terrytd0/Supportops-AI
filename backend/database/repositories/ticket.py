"""Repository for `Ticket` writes.

The first (and so far only) repository that creates a `Ticket` row --
`backend.services.ticket.TicketService` is its one caller. Until this
existed, nothing in the codebase created a real `tickets` row, which is why
`ApprovalRequestRepository.create_pending` (enqueued by
`backend.graph.nodes.persist_results_node`) had no ticket to reference for
its foreign key -- see `backend/database/README.md`.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.enums import TicketPriority, TicketStatus
from backend.database.models.ticket import Ticket


class TicketRepository:
    """Write-side repository for the `tickets` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        customer_id: uuid.UUID,
        subject: str,
        description: str,
        priority: TicketPriority,
    ) -> Ticket:
        """Create a new ticket in `TicketStatus.NEW`."""
        ticket = Ticket(
            customer_id=customer_id,
            subject=subject,
            description=description,
            priority=priority,
            status=TicketStatus.NEW,
        )
        self._session.add(ticket)
        await self._session.flush()
        return ticket
