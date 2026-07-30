"""Unit tests for confidence_evaluation_node's delegation to backend.policy.rules."""

import uuid

from backend.graph.nodes import confidence_evaluation_node
from backend.graph.state import WorkflowState


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
