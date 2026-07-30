"""Execute the compiled LangGraph support workflow against a sample ticket.

Usage:
    python -m backend.scripts.run_workflow

Exercises the graph topology and placeholder node logic end-to-end without
any external dependencies (no LLM, no database, no Redis) — useful as a
smoke test while Sprint 4 replaces individual nodes with real logic.
"""

from __future__ import annotations

import uuid
from typing import cast

from backend.core.logging import configure_logging, get_logger
from backend.graph.state import WorkflowState, WorkflowStatus
from backend.graph.workflow import get_graph

logger = get_logger(__name__)

_SAMPLE_TICKET_TEXT = "I was billed twice for my subscription."


def _initial_state() -> WorkflowState:
    """Build the input state for a single sample ticket."""
    return WorkflowState(
        ticket_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        ticket_text=_SAMPLE_TICKET_TEXT,
        workflow_status=WorkflowStatus.PENDING,
    )


def run() -> WorkflowState:
    """Invoke the compiled workflow once and return its final state."""
    graph = get_graph()
    return cast(WorkflowState, graph.invoke(_initial_state()))


def _log_state(state: WorkflowState) -> None:
    """Log the final workflow state as aligned `field: value` lines."""
    logger.info("Final workflow state:")
    width = max(len(key) for key in state)
    for key, value in state.items():
        logger.info("  %s : %s", key.ljust(width), value)


def main() -> None:
    """Entry point for `python -m backend.scripts.run_workflow`."""
    configure_logging()
    final_state = run()
    _log_state(final_state)


if __name__ == "__main__":
    main()
