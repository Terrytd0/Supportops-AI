"""LangGraph state graph package: wires agents together into a control flow.

- `state.py` — the typed `WorkflowState` threaded through every node.
- `nodes.py` — one function per workflow stage, each a deterministic
  placeholder standing in for future OpenAI/CrewAI/Postgres/Redis logic.
- `workflow.py` — assembles the nodes into the compiled graph
  (`build_workflow()` / `get_graph()`).

See `docs/adr/ADR-001-langgraph-vs-crewai.md` for why workflow orchestration
lives here (LangGraph) rather than in `backend/agents/` (CrewAI).
"""

from backend.graph.state import (
    SupportAgentType,
    TicketCategory,
    WorkflowState,
    WorkflowStatus,
)
from backend.graph.workflow import build_workflow, get_graph

__all__ = [
    "SupportAgentType",
    "TicketCategory",
    "WorkflowState",
    "WorkflowStatus",
    "build_workflow",
    "get_graph",
]
