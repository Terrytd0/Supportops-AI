"""Compiled LangGraph workflow: the permanent orchestration backbone.

Wires the nodes in `backend/graph/nodes.py` into the fixed control flow:

    START -> load_ticket -> classify_ticket -> select_agent
          -> execute_agent -> confidence_evaluation -> persist_results -> END

This topology is intended to stay stable across future Sprint work; only the
node *implementations* change (OpenAI classification, CrewAI agents,
Postgres/Redis persistence, human-approval routing). Anything that would add
a new stage or branch belongs in a topology change reviewed via ADR, not a
node-internal edit.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.graph.nodes import (
    classify_ticket_node,
    confidence_evaluation_node,
    execute_agent_node,
    load_ticket_node,
    persist_results_node,
    select_agent_node,
)
from backend.graph.state import WorkflowState

_LOAD_TICKET = "load_ticket"
_CLASSIFY_TICKET = "classify_ticket"
_SELECT_AGENT = "select_agent"
_EXECUTE_AGENT = "execute_agent"
_CONFIDENCE_EVALUATION = "confidence_evaluation"
_PERSIST_RESULTS = "persist_results"


def build_workflow() -> CompiledStateGraph:
    """Assemble and compile the support workflow graph.

    Returns a fresh compiled graph on every call; use `get_graph()` for a
    cached singleton suitable for reuse across requests.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node(_LOAD_TICKET, load_ticket_node)
    graph.add_node(_CLASSIFY_TICKET, classify_ticket_node)
    graph.add_node(_SELECT_AGENT, select_agent_node)
    graph.add_node(_EXECUTE_AGENT, execute_agent_node)
    graph.add_node(_CONFIDENCE_EVALUATION, confidence_evaluation_node)
    graph.add_node(_PERSIST_RESULTS, persist_results_node)

    graph.add_edge(START, _LOAD_TICKET)
    graph.add_edge(_LOAD_TICKET, _CLASSIFY_TICKET)
    graph.add_edge(_CLASSIFY_TICKET, _SELECT_AGENT)
    graph.add_edge(_SELECT_AGENT, _EXECUTE_AGENT)
    graph.add_edge(_EXECUTE_AGENT, _CONFIDENCE_EVALUATION)
    graph.add_edge(_CONFIDENCE_EVALUATION, _PERSIST_RESULTS)
    graph.add_edge(_PERSIST_RESULTS, END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_graph() -> CompiledStateGraph:
    """Return a process-wide cached compiled workflow instance.

    Prefer this over `build_workflow()` in application code (e.g. FastAPI
    routes/services) to avoid recompiling the graph per request.
    """
    return build_workflow()
