# backend/graph/

LangGraph state graph definitions. This is the *control flow* layer: it
defines how a support request moves through the workflow (load ticket →
classify → select agent → execute agent → confidence evaluation → persist
results), not the business rules that decide those outcomes (see
`backend/policy/`) nor the agent capabilities themselves (see
`backend/agents/`).

## Contents

- `state.py` — `WorkflowState` (the TypedDict threaded through every node)
  and its `TicketCategory` / `SupportAgentType` / `WorkflowStatus` enums.
- `nodes.py` — one function per workflow stage: `load_ticket_node`,
  `classify_ticket_node`, `select_agent_node`, `execute_agent_node`,
  `confidence_evaluation_node`, `persist_results_node`.
- `workflow.py` — `build_workflow()` / `get_graph()`, which assemble the
  nodes above into the compiled graph.

The workflow topology (`START → load_ticket → classify_ticket →
select_agent → execute_agent → confidence_evaluation → persist_results →
END`) is intended to stay fixed. See `docs/adr/ADR-001-langgraph-vs-crewai.md`
for why orchestration lives here rather than in `backend/agents/`.

## Current state: deterministic placeholders

Every node is deterministic and does no I/O — no LLM calls, no database, no
Redis. This is intentional scaffolding, not a shortcut: each node's
docstring in `nodes.py` says exactly what replaces it next.

Run `python -m backend.scripts.run_workflow` to execute the graph against a
sample ticket and see the placeholder output end to end.

## TODO

- [ ] Replace `classify_ticket_node`'s keyword matching with OpenAI-powered classification
- [ ] Replace `execute_agent_node`'s placeholder text with real CrewAI specialist agents
- [ ] Replace `confidence_evaluation_node` with a real scoring algorithm and `backend/policy/` evaluation
- [ ] Replace `persist_results_node` with repository writes (ticket, `AgentRun`, `AuditLog`)
- [ ] Configure checkpointing/persistence (e.g. backed by Postgres/Redis)
- [ ] Define human-in-the-loop interrupt points for escalation
