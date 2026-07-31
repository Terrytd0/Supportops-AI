"""Unit tests for `execute_agent_node`'s routing to the correct CrewAI agent.

Each `SpecialistAgent.respond` is monkeypatched per test -- construction is
real (see `tests/unit/agents/test_base_agent.py` for why that's safe), only
the OpenAI-calling method is replaced -- so these confirm routing and state
plumbing without ever reaching CrewAI/OpenAI. `execute_agent_node` is also
checkpointed (`@_checkpointed`), which otherwise attempts a real
(unreachable, ~0.4-0.5s) Redis connection on every call; `get_redis_client`
is monkeypatched to a `fakeredis.FakeAsyncRedis` for every test here.
"""

from __future__ import annotations

import uuid

import fakeredis
import pytest

import backend.graph.nodes as nodes
from backend.agents.account import AccountAgent
from backend.agents.base import AgentResult, SpecialistAgent
from backend.agents.billing import BillingAgent
from backend.agents.general import GeneralAgent
from backend.agents.technical import TechnicalAgent
from backend.graph.nodes import execute_agent_node
from backend.graph.state import SupportAgentType, WorkflowState


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(nodes, "get_redis_client", lambda: client)


def _state(agent_type: SupportAgentType) -> WorkflowState:
    return WorkflowState(
        ticket_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        ticket_text="irrelevant ticket text for a routing test",
        selected_agent=agent_type,
    )


def _stub_respond(agent_cls: type[SpecialistAgent], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_cls,
        "respond",
        lambda self, ticket_text: AgentResult(
            response=f"response from {agent_cls.__name__}",
            retrieved_context=f"context from {agent_cls.__name__}",
        ),
    )


def test_execute_agent_node_routes_to_billing_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_respond(BillingAgent, monkeypatch)

    result = execute_agent_node(_state(SupportAgentType.BILLING_AGENT))

    assert result["draft_response"] == "response from BillingAgent"
    assert result["retrieved_context"] == "context from BillingAgent"


def test_execute_agent_node_routes_to_technical_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_respond(TechnicalAgent, monkeypatch)

    result = execute_agent_node(_state(SupportAgentType.TECHNICAL_AGENT))

    assert result["draft_response"] == "response from TechnicalAgent"
    assert result["retrieved_context"] == "context from TechnicalAgent"


def test_execute_agent_node_routes_to_account_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_respond(AccountAgent, monkeypatch)

    result = execute_agent_node(_state(SupportAgentType.ACCOUNT_AGENT))

    assert result["draft_response"] == "response from AccountAgent"
    assert result["retrieved_context"] == "context from AccountAgent"


def test_execute_agent_node_routes_to_general_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_respond(GeneralAgent, monkeypatch)

    result = execute_agent_node(_state(SupportAgentType.GENERAL_AGENT))

    assert result["draft_response"] == "response from GeneralAgent"
    assert result["retrieved_context"] == "context from GeneralAgent"


def test_execute_agent_node_passes_through_agent_unresolved_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        BillingAgent,
        "respond",
        lambda self, ticket_text: AgentResult(
            response="fallback response",
            retrieved_context="",
            unresolved=True,
            error="OpenAI request timed out",
        ),
    )

    result = execute_agent_node(_state(SupportAgentType.BILLING_AGENT))

    assert result["draft_response"] == "fallback response"
    assert result["agent_unresolved"] is True


def test_execute_agent_node_passes_through_agent_unresolved_false_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_respond(BillingAgent, monkeypatch)

    result = execute_agent_node(_state(SupportAgentType.BILLING_AGENT))

    assert result["agent_unresolved"] is False
