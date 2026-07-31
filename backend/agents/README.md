# backend/agents/

CrewAI-powered domain specialist agents, one package per agent:

- `billing/` — invoices, refunds, payments, subscriptions, pricing.
- `technical/` — login problems, bugs, crashes, API issues, troubleshooting.
- `account/` — account settings, profile, permissions, access, user management.
- `general/` — greetings, FAQs, and anything that doesn't fit a specialist.

There is **no manager/supervisor agent**. Routing between the four is
LangGraph's job (`backend.graph.nodes.select_agent_node`), not something an
agent decides for itself.

## Architecture

```
SupportAgentType (backend/graph/state.py)
        │
        ▼
_AGENT_CLASS_BY_TYPE (backend/graph/nodes.py)
        │
        ▼
BillingAgent / TechnicalAgent / AccountAgent / GeneralAgent
        │  (all subclass)
        ▼
SpecialistAgent (backend/agents/base.py)
   ├─ builds one CrewAI Agent, LLM, Task, and single-agent Crew per call
   ├─ composes one KnowledgeBaseSearchTool (backend/tools/), scoped to
   │  the agent's CATEGORY
   └─ never raises — returns an AgentResult (response, retrieved_context,
      unresolved, optional error) even when CrewAI/OpenAI fails
```

### Shared base implementation (`base.py`)

`SpecialistAgent` is the reusable base every domain agent subclasses.
Subclasses supply four class attributes only — `ROLE`, `GOAL`, `BACKSTORY`,
`CATEGORY` — and inherit everything else:

- **LLM configuration**: `crewai.LLM`, built from `backend.config.settings`
  (`llm_model`, `openai_api_key`, `llm_temperature`,
  `llm_request_timeout_seconds`). No API key or model name is ever
  hardcoded — see `backend/config/README.md`.
- **CrewAI wiring**: one `Agent`, one `Task`, one single-agent
  `Crew(process=Process.sequential)` per `respond()` call. There's no
  multi-agent delegation or manager agent to configure. The `Task` uses
  `output_pydantic` (a small `_AgentTaskOutput` model: `response`,
  `unresolved`) so the agent returns structured output, not free text --
  this is how it reports `unresolved` to `AgentResult` without needing to
  parse its own reply.
- **Tool registration**: a `KnowledgeBaseSearchTool` instance (composition,
  not inheritance) bound to the agent's `CATEGORY`, registered on the CrewAI
  `Agent` *and* called directly by `respond()` before building the task —
  this guarantees every reply is grounded in retrieved context regardless of
  whether the LLM decides to invoke the tool itself.
- **Error handling**: `respond()` never raises. A knowledge-retrieval
  failure degrades to an empty context (logged, generation still proceeds);
  a CrewAI/OpenAI failure (timeout, API error, ...) or malformed/missing
  structured output returns a fixed fallback reply with
  `AgentResult.unresolved=True` and (for the former) `error` set.

### Reporting outcomes to policy: `AgentResult.unresolved`

Agents never decide whether a ticket needs human review -- they only
*report* whether they resolved it. `AgentResult.unresolved` is set when the
agent itself judges the knowledge-base context insufficient, it would be
guessing, or the request needs human expertise (asked for explicitly in the
task description), and always set on a CrewAI/OpenAI failure. Only
`backend.policy.rules.evaluate_policy`'s `agent_unresolved` rule turns that
signal into an escalation decision -- see `backend/policy/README.md`.

### The four agents (`billing/`, `technical/`, `account/`, `general/agent.py`)

Each is a ~10-line subclass: `ROLE`/`GOAL`/`BACKSTORY` (CrewAI role
definition) plus `CATEGORY` (which knowledge-base slice and
`SupportAgentType` it corresponds to). No agent implements retrieval,
LLM setup, or error handling itself.

## Interaction with `backend/graph`

`backend.graph.nodes.execute_agent_node` is the only caller:

1. Reads `state["selected_agent"]` (a `SupportAgentType`, set upstream by
   `select_agent_node`).
2. Looks it up in `_AGENT_CLASS_BY_TYPE` and instantiates that
   `SpecialistAgent` subclass.
3. Calls `agent.respond(state["ticket_text"])`.
4. Writes `draft_response` / `retrieved_context` / `agent_unresolved` back
   into `WorkflowState`. `confidence_evaluation_node` passes
   `agent_unresolved` straight through to
   `backend.policy.rules.evaluate_policy`, which is the only place that
   decides whether it forces human review.

The graph topology (`backend/graph/workflow.py`) is unchanged. Agents
define *capability*; LangGraph still owns *control flow*; `backend/policy/`
still owns the escalation decision -- agents report an outcome, they never
decide it.

## Interaction with `backend/tools`

Agents consume tools, never touch the database directly. Today that's a
single tool, `backend.tools.knowledge_base.KnowledgeBaseSearchTool`, which
wraps `backend.database.repositories.knowledge_article
.KnowledgeArticleRepository` (a real Postgres query, ranked by keyword
overlap, Redis-cached) behind CrewAI's synchronous `BaseTool` interface. See
`backend/tools/README.md` for how the sync/async bridge and cache work.

## Testing

Every agent constructs real CrewAI `Agent`/`Task`/`Crew`/tool objects in
tests (safe — construction makes no network call); only `Crew.kickoff` and
`KnowledgeBaseSearchTool.run` are mocked, so tests never depend on exact LLM
wording and never reach OpenAI or Postgres. See:

- `tests/unit/agents/test_base_agent.py` — base-class behavior (success,
  tool invocation, generation failure, retrieval failure, `unresolved`
  passthrough).
- `tests/unit/graph/test_execute_agent_node.py` — routing from each
  `SupportAgentType` to its agent class, and `agent_unresolved` passthrough.
- `tests/unit/policy/test_rules.py` — the `agent_unresolved` policy rule.
