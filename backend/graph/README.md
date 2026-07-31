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
- `classifier.py` — `classify_ticket`, an OpenAI structured-output call used
  only by `classify_ticket_node`. Not a CrewAI agent -- an internal
  orchestration helper. Redis-cached (`backend.core.cache.RedisCache`) by
  normalized ticket text, so a repeated ticket skips the OpenAI call.
- `checkpoint.py` — `WorkflowCheckpointStore`, a best-effort Redis snapshot
  of the latest completed stage's state, saved after four of the nodes
  below via `nodes.py`'s `@_checkpointed` decorator. Not LangGraph's native
  checkpointer -- see the module docstring for why.
- `nodes.py` — one function per workflow stage: `load_ticket_node`,
  `classify_ticket_node`, `select_agent_node`, `execute_agent_node`,
  `confidence_evaluation_node`, `persist_results_node`.
- `workflow.py` — `build_workflow()` / `get_graph()`, which assemble the
  nodes above into the compiled graph.

The workflow topology (`START → load_ticket → classify_ticket →
select_agent → execute_agent → confidence_evaluation → persist_results →
END`) is intended to stay fixed. See `docs/adr/ADR-001-langgraph-vs-crewai.md`
for why orchestration lives here rather than in `backend/agents/`.

## Current state

- `classify_ticket_node` calls `classifier.classify_ticket` (OpenAI
  structured outputs, constrained to `TicketCategory`) instead of keyword
  matching. Never raises; falls back to `TicketCategory.GENERAL` on any
  failure (timeout, malformed response, an out-of-enum value).
- `select_agent_node` is still a deterministic category→agent mapping.
- `execute_agent_node` calls a real CrewAI specialist agent
  (`backend/agents/`): an OpenAI call plus a Postgres knowledge-base read.
  It reports `agent_unresolved` (set on a generation failure, or the
  agent's own "I can't confidently answer this" signal) into state --
  agents never decide to escalate themselves.
- `confidence_evaluation_node` passes `agent_unresolved` and a (still
  placeholder) confidence score to `backend.policy.rules.evaluate_policy`,
  the only component that decides `requires_human_review`, and returns
  `matched_policy_rules` alongside it.
- `persist_results_node` enqueues a real supervisor-queue row
  (`ApprovalRequest` via `ApprovalRequestRepository`) plus an
  `ai_draft_created` audit event when `requires_human_review` is set --
  best-effort, never crashes the workflow. See `backend/api/README.md` /
  `backend/database/README.md` for the queue itself.

`classify_ticket_node` and `execute_agent_node` are the nodes that perform
I/O (both OpenAI calls); neither raises. Four nodes (classification, agent
selection, specialist execution, policy evaluation) also save a best-effort
Redis checkpoint after they run (`@_checkpointed`, `checkpoint.py`) --
diagnostic/recovery only, never required for correctness.

Run `python -m backend.scripts.run_workflow` to execute the graph against a
sample ticket end to end (requires a reachable OpenAI API key; the
knowledge-base lookup, classification/knowledge caches, checkpoint saves,
and supervisor-queue write all degrade gracefully without Postgres/Redis).
`POST /tickets` (`backend/api/routes/tickets.py`) is the real HTTP entry
point into this same graph, via `backend.services.ticket.create_ticket`.

## TODO

- [ ] Replace `confidence_evaluation_node`'s placeholder score with a real, model-derived one
- [ ] `persist_results_node`: also write an `AgentRun` row (the `Ticket` itself
      is now created by `backend.services.ticket.create_ticket` before the
      graph runs, not by this node) and update `tickets.status` to reflect
      the workflow's outcome -- today a ticket is created `NEW` and nothing
      ever moves it through `docs/database_schema.md`'s documented Status
      Flow; only `approval_requests.status` reflects a supervisor decision
- [ ] Define human-in-the-loop interrupt points for escalation
