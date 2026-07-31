"""Unit tests for confidence_evaluation_node's delegation to backend.policy.rules.

`confidence_evaluation_node` is checkpointed (`@_checkpointed`), which
otherwise attempts a real (unreachable, ~0.4-0.5s) Redis connection on every
call; `get_redis_client` is monkeypatched to a `fakeredis.FakeAsyncRedis`
for every test in this module to avoid that tax.
"""

import uuid

import fakeredis
import pytest

import backend.graph.nodes as nodes
from backend.graph.nodes import confidence_evaluation_node
from backend.graph.state import WorkflowState


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(nodes, "get_redis_client", lambda: client)


def _state(ticket_text: str) -> WorkflowState:
    return WorkflowState(
        ticket_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        ticket_text=ticket_text,
    )


def test_confidence_evaluation_node_no_review_needed() -> None:
    result = confidence_evaluation_node(_state("My app keeps crashing on login."))
    assert result["requires_human_review"] is False
    assert "confidence_score" in result


def test_confidence_evaluation_node_flags_escalation_keyword() -> None:
    result = confidence_evaluation_node(_state("I want to speak to my attorney about a breach."))
    assert result["requires_human_review"] is True


def test_confidence_evaluation_node_returns_matched_policy_rules() -> None:
    result = confidence_evaluation_node(_state("I want to speak to my attorney about a breach."))
    assert "attorney" in result["matched_policy_rules"]
    assert "breach" in result["matched_policy_rules"]


def test_confidence_evaluation_node_escalates_on_agent_unresolved() -> None:
    """`agent_unresolved` (set by execute_agent_node -- a generation failure,
    or the agent's own "I can't confidently answer this" signal) must reach
    policy and force review, even with no keyword match and high confidence."""
    state = _state("My app keeps crashing on login.")
    state["agent_unresolved"] = True

    result = confidence_evaluation_node(state)

    assert result["requires_human_review"] is True
    assert "agent_unresolved" in result["matched_policy_rules"]


def test_confidence_evaluation_node_does_not_escalate_when_agent_resolved() -> None:
    """Absence of `agent_unresolved` in state (the normal case) behaves exactly
    as it did before the signal existed."""
    result = confidence_evaluation_node(_state("My app keeps crashing on login."))
    assert result["requires_human_review"] is False
    assert "agent_unresolved" not in result["matched_policy_rules"]
