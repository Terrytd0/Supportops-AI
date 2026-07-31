"""Shared CrewAI agent abstraction for every domain specialist agent.

`SpecialistAgent` encapsulates everything the four domain agents
(`backend/agents/{billing,technical,account,general}/`) have in common:
CrewAI `Agent`/`Task`/`Crew` construction, LLM configuration (sourced from
`backend.config.settings`, never hardcoded), knowledge-base tool
registration/invocation, and graceful error handling. Subclasses supply only
data -- `ROLE`, `GOAL`, `BACKSTORY`, `CATEGORY` -- composing in a
`KnowledgeBaseSearchTool` scoped to that category rather than each
reimplementing retrieval (composition over inheritance for the one piece of
real behavior that varies).

`backend.graph.nodes.execute_agent_node` is the only caller: it selects a
subclass by `SupportAgentType`, instantiates it, and calls `respond()`.
"""

from __future__ import annotations

from dataclasses import dataclass

from crewai import LLM, Agent, Crew, Process, Task
from crewai.crews.crew_output import CrewOutput
from pydantic import BaseModel

from backend.config.settings import get_settings
from backend.core.logging import get_logger
from backend.tools.knowledge_base import KnowledgeBaseSearchTool

logger = get_logger(__name__)

_EXPECTED_OUTPUT = (
    "A JSON object matching the given schema: a concise, professional support "
    "reply addressed directly to the customer, grounded only in the ticket "
    "text and any retrieved knowledge-base context, plus whether the ticket "
    "remains unresolved."
)

_FALLBACK_RESPONSE = (
    "We're sorry -- we weren't able to generate an automated response for this "
    "ticket right now. It has been queued for a human support agent to review."
)


class _AgentTaskOutput(BaseModel):
    """Structured CrewAI task output (`Task.output_pydantic`).

    Asking the agent to self-report `unresolved` -- rather than inferring it
    from the response text -- is how it communicates a structured execution
    outcome to the policy engine (via `AgentResult`/`WorkflowState`) without
    ever deciding escalation itself; only `backend.policy.rules.evaluate_policy`
    does that.
    """

    response: str
    unresolved: bool


@dataclass(frozen=True)
class AgentResult:
    """Outcome of a single `SpecialistAgent.respond()` call.

    `unresolved` is the structured signal the policy engine reacts to (its
    `agent_unresolved` rule) -- set by the agent itself when it judges
    knowledge retrieval insufficient, it would be guessing, or the request
    needs human expertise, and always set on a CrewAI/OpenAI failure
    (`error` is set in that case too, and `response` is `_FALLBACK_RESPONSE`).
    The agent only *reports* this; it never escalates on its own.
    """

    response: str
    retrieved_context: str
    unresolved: bool = False
    error: str | None = None


class SpecialistAgent:
    """Base class for a single-agent, single-task CrewAI crew.

    Subclasses set the class attributes below; everything else (LLM setup,
    tool registration, task/crew wiring, error handling) lives here once.
    """

    ROLE: str
    GOAL: str
    BACKSTORY: str
    CATEGORY: str

    def __init__(self) -> None:
        settings = get_settings()
        self._knowledge_tool = KnowledgeBaseSearchTool(category=self.CATEGORY)
        llm = LLM(
            model=settings.llm_model,
            api_key=settings.openai_api_key or None,
            temperature=settings.llm_temperature,
            timeout=settings.llm_request_timeout_seconds,
        )
        self._agent = Agent(
            role=self.ROLE,
            goal=self.GOAL,
            backstory=self.BACKSTORY,
            tools=[self._knowledge_tool],
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )

    def respond(self, ticket_text: str) -> AgentResult:
        """Retrieve grounding context, then generate a reply. Never raises."""
        retrieved_context = self._retrieve_context(ticket_text)

        task = Task(
            description=self._task_description(ticket_text, retrieved_context),
            expected_output=_EXPECTED_OUTPUT,
            agent=self._agent,
            output_pydantic=_AgentTaskOutput,
        )
        crew = Crew(
            agents=[self._agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
        )

        logger.info(
            "OpenAI request starting",
            extra={"agent_role": self.ROLE, "tools": [self._knowledge_tool.name]},
        )
        try:
            output = crew.kickoff()
        except Exception as exc:
            logger.error(
                "Agent generation failed",
                extra={"agent_role": self.ROLE, "error": str(exc)},
            )
            return AgentResult(
                response=_FALLBACK_RESPONSE,
                retrieved_context=retrieved_context,
                unresolved=True,
                error=str(exc),
            )

        parsed = output.pydantic if isinstance(output, CrewOutput) else None
        if not isinstance(parsed, _AgentTaskOutput):
            logger.warning(
                "Agent returned unstructured or malformed output; treating as unresolved",
                extra={"agent_role": self.ROLE},
            )
            return AgentResult(
                response=str(output), retrieved_context=retrieved_context, unresolved=True
            )

        logger.info("OpenAI request completed", extra={"agent_role": self.ROLE})
        return AgentResult(
            response=parsed.response,
            retrieved_context=retrieved_context,
            unresolved=parsed.unresolved,
        )

    def _retrieve_context(self, ticket_text: str) -> str:
        """Call the knowledge-base tool directly, guaranteeing a grounded task
        description regardless of whether the LLM decides to invoke it itself.

        The tool never raises (see `KnowledgeBaseSearchTool._run`); this
        try/except is defense-in-depth against a future tool that doesn't
        honor that contract, per the "never crash the workflow" requirement.
        """
        try:
            context = self._knowledge_tool.run(query=ticket_text)
        except Exception as exc:
            logger.warning(
                "Knowledge retrieval failed", extra={"agent_role": self.ROLE, "error": str(exc)}
            )
            return ""
        return str(context) if context else ""

    def _task_description(self, ticket_text: str, retrieved_context: str) -> str:
        return (
            f"A customer submitted this support ticket:\n"
            f'"""\n{ticket_text}\n"""\n\n'
            f"Relevant knowledge-base context:\n"
            f'"""\n{retrieved_context}\n"""\n\n'
            "Write a helpful, professional, and concise reply grounded only in "
            "the ticket text and the knowledge-base context above.\n\n"
            "Also set `unresolved` to true if any of the following applies, "
            "false otherwise:\n"
            "- the knowledge-base context above is insufficient to answer\n"
            "- you would be guessing rather than answering from the ticket "
            "text and context\n"
            "- the request requires human judgment or expertise you don't have\n"
            "You are not deciding whether a human reviews this ticket -- you "
            "are only reporting whether you were able to resolve it."
        )
