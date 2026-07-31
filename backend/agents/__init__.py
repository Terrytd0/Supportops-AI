"""CrewAI domain specialist agents: billing, technical, account, and general.

There is no manager/supervisor agent -- `backend.graph.nodes.select_agent_node`
(LangGraph) picks which of these four handles a ticket; `execute_agent_node`
instantiates it and calls `respond()`. See `backend/agents/README.md` for the
full architecture.
"""

from backend.agents.account import AccountAgent
from backend.agents.base import AgentResult, SpecialistAgent
from backend.agents.billing import BillingAgent
from backend.agents.general import GeneralAgent
from backend.agents.technical import TechnicalAgent

__all__ = [
    "AccountAgent",
    "AgentResult",
    "BillingAgent",
    "GeneralAgent",
    "SpecialistAgent",
    "TechnicalAgent",
]
