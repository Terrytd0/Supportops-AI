"""Unit tests for `persist_results_node`'s supervisor-queue enqueueing.

`ApprovalRequestRepository.create_pending` and `log_audit_event` are
monkeypatched (no test database exists yet -- see
`tests/unit/core/test_rate_limit.py`), so these confirm *whether* a review
item is enqueued (policy's decision, already in state as
`requires_human_review`), not the repository's own persistence logic
(covered by `tests/unit/database/repositories/test_knowledge_article.py`-style
tests elsewhere).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from backend.database.repositories.approval_request import ApprovalRequestRepository
from backend.graph.nodes import persist_results_node
from backend.graph.state import SupportAgentType, WorkflowState, WorkflowStatus


def _state(*, requires_human_review: bool) -> WorkflowState:
    return WorkflowState(
        ticket_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        ticket_text="My app keeps crashing on login.",
        selected_agent=SupportAgentType.TECHNICAL_AGENT,
        draft_response="Here is a troubleshooting reply.",
        retrieved_context="Some KB context.",
        requires_human_review=requires_human_review,
        matched_policy_rules=("agent_unresolved",),
    )


@pytest.fixture(autouse=True)
def _no_op_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test gets a no-op session and a no-op `log_audit_event` by
    default: unmocked, `log_audit_event` attempts a real (unreachable,
    ~2-3s-to-fail) Postgres connection on every call. The dedicated audit
    test below overrides this with a capturing version."""

    class _NoOpSession:
        async def __aenter__(self) -> _NoOpSession:
            return self

        async def __aexit__(self, *exc_info: object) -> bool:
            return False

        async def commit(self) -> None:
            pass

    async def _noop_log_audit_event(**_kwargs: Any) -> None:
        pass

    monkeypatch.setattr("backend.graph.nodes.async_session_factory", lambda: _NoOpSession())
    monkeypatch.setattr("backend.graph.nodes.log_audit_event", _noop_log_audit_event)


def test_persist_results_node_enqueues_review_when_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create_pending(self: ApprovalRequestRepository, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(ApprovalRequestRepository, "create_pending", fake_create_pending)

    state = _state(requires_human_review=True)
    result = persist_results_node(state)

    assert captured["ticket_id"] == state["ticket_id"]
    assert captured["draft_response"] == "Here is a troubleshooting reply."
    assert captured["selected_agent"] == "technical_agent"
    assert captured["matched_policy_rules"] == ["agent_unresolved"]
    assert result["workflow_status"] == WorkflowStatus.COMPLETED


def test_persist_results_node_logs_ai_draft_created_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create_pending(self: ApprovalRequestRepository, **kwargs: Any) -> None:
        pass

    audit_calls: list[dict[str, Any]] = []

    async def fake_log_audit_event(**kwargs: Any) -> None:
        audit_calls.append(kwargs)

    monkeypatch.setattr(ApprovalRequestRepository, "create_pending", fake_create_pending)
    monkeypatch.setattr("backend.graph.nodes.log_audit_event", fake_log_audit_event)

    persist_results_node(_state(requires_human_review=True))

    assert len(audit_calls) == 1
    assert audit_calls[0]["event_type"] == "ai_draft_created"


def test_persist_results_node_does_not_enqueue_when_not_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_create_pending(self: ApprovalRequestRepository, **kwargs: Any) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(ApprovalRequestRepository, "create_pending", fake_create_pending)

    result = persist_results_node(_state(requires_human_review=False))

    assert called is False
    assert result["workflow_status"] == WorkflowStatus.COMPLETED


def test_persist_results_node_never_raises_when_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `Ticket` row exists for `ticket_id` in this scaffold (no
    ticket-creation flow yet), so a real FK-violation-style failure here is
    expected -- it must never crash the workflow."""

    async def failing_create_pending(self: ApprovalRequestRepository, **kwargs: Any) -> None:
        raise RuntimeError("insert or update on table violates foreign key constraint")

    monkeypatch.setattr(ApprovalRequestRepository, "create_pending", failing_create_pending)

    result = persist_results_node(_state(requires_human_review=True))

    assert result["workflow_status"] == WorkflowStatus.COMPLETED
