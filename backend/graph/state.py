"""Typed state schema for the LangGraph support workflow.

`WorkflowState` is the single object threaded through every node in
`backend/graph/workflow.py`. Nodes read the fields they need and return a
partial update (a `dict` covering only the keys they set); LangGraph merges
that update into the running state.

This module defines *shape only* — no classification, scoring, or persistence
logic. `TicketCategory` and `SupportAgentType` are workflow-level vocabularies
(they describe what the graph can route to), independent of any future
CrewAI role names or the `backend.database.enums` schema-backed enums.
"""

from __future__ import annotations

import enum
from typing import NotRequired, TypedDict
from uuid import UUID


class TicketCategory(str, enum.Enum):
    """Routing category assigned by `classify_ticket_node`."""

    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"


class SupportAgentType(str, enum.Enum):
    """Specialist agent assigned by `select_agent_node`.

    Names mirror `TicketCategory` today (one agent per category); the two
    enums are kept separate because future routing (e.g. load balancing
    across multiple technical agents) may make that mapping non 1:1.
    """

    BILLING_AGENT = "billing_agent"
    TECHNICAL_AGENT = "technical_agent"
    ACCOUNT_AGENT = "account_agent"
    GENERAL_AGENT = "general_agent"


class WorkflowStatus(str, enum.Enum):
    """Lifecycle status of a workflow run, distinct from `TicketStatus`.

    `TicketStatus` (`backend.database.enums`) tracks the ticket's business
    lifecycle in Postgres. `WorkflowStatus` tracks this in-memory graph
    invocation and has no persisted counterpart yet.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class WorkflowState(TypedDict):
    """State threaded through every node of the support workflow graph."""

    ticket_id: UUID
    customer_id: UUID
    ticket_text: str

    category: NotRequired[TicketCategory]
    selected_agent: NotRequired[SupportAgentType]
    retrieved_context: NotRequired[str]
    draft_response: NotRequired[str]
    agent_unresolved: NotRequired[bool]
    confidence_score: NotRequired[float]
    requires_human_review: NotRequired[bool]
    matched_policy_rules: NotRequired[tuple[str, ...]]
    workflow_status: NotRequired[WorkflowStatus]
