"""Pydantic schemas for ticket creation (`backend/api/routes/tickets.py`).

`category`/`selected_agent` are plain strings, not
`backend.graph.state`'s `TicketCategory`/`SupportAgentType` enums -- the
same choice `backend/schemas/supervisor.py` made, so this boundary layer
doesn't couple to the graph layer's specific vocabulary types.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.database.enums import TicketPriority


class TicketCreateRequest(BaseModel):
    """Request body for `POST /tickets`."""

    customer_id: uuid.UUID
    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketCreateResponse(BaseModel):
    """Response body for `POST /tickets`.

    Reflects the full LangGraph workflow run triggered by ticket creation
    (classification, specialist response, policy evaluation) -- not just
    the persisted `Ticket` row.
    """

    ticket_id: uuid.UUID
    customer_id: uuid.UUID
    category: str
    selected_agent: str
    draft_response: str
    requires_human_review: bool
    matched_policy_rules: list[str]
    created_at: datetime
    idempotent_replay: bool = False
