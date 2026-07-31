"""Unit tests for `SpecialistAgent`, the base class shared by every domain agent.

Constructing real CrewAI `Agent`/`Task`/`Crew`/tool objects makes no network
call (only `Crew.kickoff()` does), so these tests build a real
`SpecialistAgent` subclass and mock only `Crew.kickoff` (never reaching
OpenAI) and `KnowledgeBaseSearchTool.run` (never reaching Postgres) --
per the "mock OpenAI, don't assert on exact LLM wording" testing requirement.
"""

from __future__ import annotations

from typing import Any

import pytest
from crewai import Crew

from backend.agents.base import SpecialistAgent
from backend.tools.knowledge_base import KnowledgeBaseSearchTool


class _FakeAgent(SpecialistAgent):
    ROLE = "Fake Support Specialist"
    GOAL = "Answer test tickets."
    BACKSTORY = "A specialist agent used only in tests."
    CATEGORY = "general"


@pytest.fixture(autouse=True)
def _no_real_knowledge_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module avoids a real Postgres connection by default."""

    def fake_run(self: KnowledgeBaseSearchTool, **kwargs: Any) -> str:
        return "Relevant knowledge-base context."

    monkeypatch.setattr(KnowledgeBaseSearchTool, "run", fake_run)


def test_respond_returns_generated_text_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Crew, "kickoff", lambda self, *a, **kw: "Here is your answer.")

    result = _FakeAgent().respond("How do I reset my password?")

    assert result.response == "Here is your answer."
    assert result.retrieved_context == "Relevant knowledge-base context."
    assert result.error is None


def test_respond_invokes_the_knowledge_tool_with_the_ticket_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Crew, "kickoff", lambda self, *a, **kw: "ok")
    seen_queries: list[str] = []

    def fake_run(self: KnowledgeBaseSearchTool, **kwargs: Any) -> str:
        seen_queries.append(kwargs["query"])
        return "context"

    monkeypatch.setattr(KnowledgeBaseSearchTool, "run", fake_run)

    _FakeAgent().respond("My login keeps failing.")

    assert seen_queries == ["My login keeps failing."]


def test_respond_falls_back_gracefully_when_crew_kickoff_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_kickoff(self: Crew, *args: Any, **kwargs: Any) -> str:
        raise RuntimeError("OpenAI request timed out")

    monkeypatch.setattr(Crew, "kickoff", failing_kickoff)

    result = _FakeAgent().respond("Anything.")

    assert result.error == "OpenAI request timed out"
    assert "queued for a human support agent" in result.response


def test_respond_still_generates_when_knowledge_retrieval_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Crew, "kickoff", lambda self, *a, **kw: "Here is your answer.")

    def failing_run(self: KnowledgeBaseSearchTool, **kwargs: Any) -> str:
        raise RuntimeError("knowledge base unreachable")

    monkeypatch.setattr(KnowledgeBaseSearchTool, "run", failing_run)

    result = _FakeAgent().respond("Anything.")

    assert result.retrieved_context == ""
    assert result.response == "Here is your answer."
    assert result.error is None
