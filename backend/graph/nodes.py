"""Node implementations for the support workflow graph.

Every node is a plain function `(WorkflowState) -> dict` — the LangGraph
convention of returning a partial state update rather than the full state.
Each one is wired to the correct field(s) of `WorkflowState` so the graph
topology in `backend/graph/workflow.py` never has to change when a
placeholder is replaced with real logic:

- `classify_ticket_node` calls `backend.graph.classifier.classify_ticket`,
  an OpenAI structured-output call (not a CrewAI agent).
- `execute_agent_node` instantiates the `SpecialistAgent` subclass
  (`backend/agents/`) selected by `select_agent_node` and generates a real,
  knowledge-grounded reply via CrewAI, reporting an `agent_unresolved`
  signal the policy engine factors into its escalation decision.
- `confidence_evaluation_node` will be replaced by a real scoring algorithm;
  it already delegates the human-approval decision to `backend/policy/`.
- `persist_results_node` will be replaced by full repository writes to
  Postgres (it already persists a supervisor review item when required).

`classify_ticket_node` and `execute_agent_node` are the nodes that perform
I/O (both OpenAI calls); `execute_agent_node` also reads Postgres via its
agent's knowledge-base tool. None of them raise -- see
`backend.graph.classifier.classify_ticket` and
`backend.agents.base.SpecialistAgent`.

Four nodes (classification, agent selection, specialist execution, policy
evaluation) are wrapped with `@_checkpointed(stage=...)`, saving a
best-effort Redis snapshot after each via
`backend.graph.checkpoint.WorkflowCheckpointStore` -- see that module for
why this isn't LangGraph's native checkpointer. Purely diagnostic/
recovery-oriented: a checkpoint failure never affects the node's own return
value or the graph's control flow.
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from backend.agents.account import AccountAgent
from backend.agents.base import SpecialistAgent
from backend.agents.billing import BillingAgent
from backend.agents.general import GeneralAgent
from backend.agents.technical import TechnicalAgent
from backend.config.settings import get_settings
from backend.core.asyncio_utils import run_sync
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis_client
from backend.database.repositories.approval_request import ApprovalRequestRepository
from backend.database.session import async_session_factory
from backend.graph.checkpoint import WorkflowCheckpointStore
from backend.graph.classifier import classify_ticket
from backend.graph.state import (
    SupportAgentType,
    TicketCategory,
    WorkflowState,
    WorkflowStatus,
)
from backend.policy.rules import evaluate_policy
from backend.services.audit import log_audit_event

logger = get_logger(__name__)


_NodeFn = TypeVar("_NodeFn", bound=Callable[[WorkflowState], dict])


async def _save_checkpoint(*, ticket_id: uuid.UUID, stage: str, snapshot: dict[str, Any]) -> None:
    """Resolve this call's Redis client and save one checkpoint.

    Constructing `WorkflowCheckpointStore` here, inside the coroutine
    `run_sync` executes, rather than in `_checkpointed`'s plain sync
    wrapper, matters: `get_redis_client()` requires a running event loop,
    and must resolve to the loop `run_sync` actually runs on -- see
    `backend/core/redis_client.py`'s module docstring.
    """
    settings = get_settings()
    store = WorkflowCheckpointStore(
        get_redis_client(), ttl_seconds=settings.redis_checkpoint_ttl_seconds
    )
    await store.save(ticket_id=ticket_id, stage=stage, snapshot=snapshot)


def _checkpointed(stage: str) -> Callable[[_NodeFn], _NodeFn]:
    """Save a best-effort Redis checkpoint after a node runs, without
    touching its return value, its declared type, or the graph topology.

    A checkpoint failure is caught and logged here, never propagated -- see
    `backend.graph.checkpoint.WorkflowCheckpointStore` for the (already
    fail-open) store itself; this is defense-in-depth against anything else
    going wrong while building the snapshot.
    """

    def decorator(node_fn: _NodeFn) -> _NodeFn:
        @functools.wraps(node_fn)
        def wrapper(state: WorkflowState) -> dict:
            update = node_fn(state)
            try:
                run_sync(
                    _save_checkpoint(ticket_id=state["ticket_id"], stage=stage, snapshot=update)
                )
            except Exception as exc:
                logger.warning(
                    "Checkpoint bookkeeping failed",
                    extra={"ticket_id": str(state["ticket_id"]), "stage": stage, "error": str(exc)},
                )
            return update

        return wrapper  # type: ignore[return-value]

    return decorator


# Placeholder confidence score used until execute_agent_node/classify_ticket_node
# call a real model for it too. TODO(OpenAI): replace with a score derived
# from the LLM's own output (e.g. logprobs, a self-rated confidence field).
_PLACEHOLDER_CONFIDENCE_SCORE = 1.0

# Category -> specialist agent. Kept as an explicit mapping (rather than
# deriving one enum from the other) so a future many-agents-per-category
# change only touches this dict.
_AGENT_BY_CATEGORY: dict[TicketCategory, SupportAgentType] = {
    TicketCategory.BILLING: SupportAgentType.BILLING_AGENT,
    TicketCategory.TECHNICAL: SupportAgentType.TECHNICAL_AGENT,
    TicketCategory.ACCOUNT: SupportAgentType.ACCOUNT_AGENT,
    TicketCategory.GENERAL: SupportAgentType.GENERAL_AGENT,
}

# SupportAgentType -> the SpecialistAgent subclass execute_agent_node
# instantiates. One dict, so adding a fifth agent only ever touches this
# mapping (plus backend/graph/state.py and backend/agents/).
_AGENT_CLASS_BY_TYPE: dict[SupportAgentType, type[SpecialistAgent]] = {
    SupportAgentType.BILLING_AGENT: BillingAgent,
    SupportAgentType.TECHNICAL_AGENT: TechnicalAgent,
    SupportAgentType.ACCOUNT_AGENT: AccountAgent,
    SupportAgentType.GENERAL_AGENT: GeneralAgent,
}


def load_ticket_node(state: WorkflowState) -> dict:
    """Placeholder ingestion step: pass the incoming ticket through unchanged.

    No database access. Future work replaces this with a repository lookup
    (`backend/database/repositories/`) that fetches the ticket by
    `ticket_id` instead of trusting the caller-supplied fields.
    """
    logger.info("Workflow started for ticket %s", state["ticket_id"])
    return {
        "ticket_id": state["ticket_id"],
        "customer_id": state["customer_id"],
        "ticket_text": state["ticket_text"],
    }


@_checkpointed(stage="classification")
def classify_ticket_node(state: WorkflowState) -> dict:
    """Assign a `TicketCategory` via `backend.graph.classifier.classify_ticket`.

    Not a CrewAI agent -- a direct OpenAI structured-output call. Never
    raises; any failure already falls back to `TicketCategory.GENERAL`
    inside `classify_ticket` itself.
    """
    category = classify_ticket(state["ticket_text"])
    logger.info("Ticket %s classified as %s", state["ticket_id"], category.value)
    return {"category": category}


@_checkpointed(stage="agent_selection")
def select_agent_node(state: WorkflowState) -> dict:
    """Map `category` to the specialist agent that will handle the ticket.

    No CrewAI implementation. Future work replaces the mapping's targets
    (or adds load-balancing logic) without changing this node's contract.
    """
    category = state.get("category", TicketCategory.GENERAL)
    agent = _AGENT_BY_CATEGORY[category]
    logger.info("Ticket %s routed to %s", state["ticket_id"], agent.value)
    return {"selected_agent": agent}


@_checkpointed(stage="specialist_execution")
def execute_agent_node(state: WorkflowState) -> dict:
    """Instantiate `selected_agent`'s CrewAI agent and generate a real reply.

    Delegates entirely to `backend.agents.base.SpecialistAgent.respond()`,
    which retrieves knowledge-base context, calls OpenAI via CrewAI, and
    never raises. `result.unresolved` -- set on a generation failure, or
    self-reported by the agent when it can't confidently answer -- is
    passed through as-is; `confidence_evaluation_node` is the one place
    that turns it into an escalation decision.
    """
    agent_type = state.get("selected_agent", SupportAgentType.GENERAL_AGENT)
    agent_cls = _AGENT_CLASS_BY_TYPE[agent_type]
    agent = agent_cls()

    logger.info("Ticket %s executing via %s", state["ticket_id"], agent_type.value)
    result = agent.respond(state["ticket_text"])

    return {
        "retrieved_context": result.retrieved_context,
        "draft_response": result.response,
        "agent_unresolved": result.unresolved,
    }


@_checkpointed(stage="policy_evaluation")
def confidence_evaluation_node(state: WorkflowState) -> dict:
    """Score the draft response and delegate the human-review decision to policy.

    The node itself holds no business rules: it supplies a confidence
    score, the ticket text, and `agent_unresolved` (set by
    `execute_agent_node`, e.g. on a CrewAI/OpenAI failure or the agent's own
    "I can't confidently answer this" signal) to
    `backend.policy.rules.evaluate_policy`, which owns every rule that
    decides `requires_human_review` -- including the new `agent_unresolved`
    rule. Agents never decide to escalate themselves; they only report an
    outcome for policy to evaluate.

    TODO(OpenAI): replace `_PLACEHOLDER_CONFIDENCE_SCORE` with a real,
    model-derived score.
    """
    confidence_score = _PLACEHOLDER_CONFIDENCE_SCORE
    evaluation = evaluate_policy(
        ticket_text=state["ticket_text"],
        confidence_score=confidence_score,
        agent_unresolved=state.get("agent_unresolved", False),
    )
    logger.info(
        "Policy evaluation for ticket %s: requires_human_review=%s (rules=%s)",
        state["ticket_id"],
        evaluation.requires_human_review,
        evaluation.matched_rules,
    )
    return {
        "confidence_score": confidence_score,
        "requires_human_review": evaluation.requires_human_review,
        "matched_policy_rules": evaluation.matched_rules,
    }


def persist_results_node(state: WorkflowState) -> dict:
    """Enqueue a supervisor review item when required; mark the run completed.

    Policy (`confidence_evaluation_node`) already decided
    `requires_human_review` -- this node never makes that decision, it only
    persists the outcome. No Postgres access happens when review isn't
    required. Future work adds the remaining repository writes (the ticket
    itself, an `AgentRun` row), keeping `workflow_status` as the last field
    set.
    """
    if state.get("requires_human_review"):
        _enqueue_supervisor_review(state)
    logger.info("Workflow completed for ticket %s", state["ticket_id"])
    return {"workflow_status": WorkflowStatus.COMPLETED}


def _enqueue_supervisor_review(state: WorkflowState) -> None:
    """Persist a pending `ApprovalRequest` plus an "ai_draft_created" audit event.

    Best-effort and never raises: this requires a `Ticket` row already
    existing in Postgres for `ticket_id` (an FK this scaffold doesn't yet
    have a ticket-creation flow to satisfy -- see
    `backend/database/repositories/__init__.py`'s TODO), so a failure here
    is expected until that exists, and must not crash the workflow.
    """
    matched_policy_rules = list(state.get("matched_policy_rules", ()))
    selected_agent = state.get("selected_agent", SupportAgentType.GENERAL_AGENT)

    async def _persist() -> None:
        async with async_session_factory() as session:
            repository = ApprovalRequestRepository(session)
            await repository.create_pending(
                ticket_id=state["ticket_id"],
                draft_response=state.get("draft_response", ""),
                retrieved_context=state.get("retrieved_context"),
                selected_agent=selected_agent.value,
                matched_policy_rules=matched_policy_rules,
            )
            await session.commit()
        await log_audit_event(
            ticket_id=state["ticket_id"],
            event_type="ai_draft_created",
            description="AI generated a draft response requiring supervisor review.",
            metadata={"matched_policy_rules": matched_policy_rules},
        )

    try:
        run_sync(_persist())
    except Exception as exc:
        logger.warning(
            "Failed to enqueue supervisor review item",
            extra={"ticket_id": str(state["ticket_id"]), "error": str(exc)},
        )
