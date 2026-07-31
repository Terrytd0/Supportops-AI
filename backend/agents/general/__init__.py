"""General support agent: greetings, FAQs, and fallback handling for tickets
that don't fit a specialist agent.

Note: this is a domain specialist like the other three agents, not a
manager/router -- routing between agents is LangGraph's job
(`backend.graph.nodes.select_agent_node`), not this agent's.
"""

from backend.agents.general.agent import GeneralAgent

__all__ = ["GeneralAgent"]
