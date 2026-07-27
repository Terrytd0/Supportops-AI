# backend/graph/

LangGraph state graph definitions. This is the *control flow* layer: it
defines how a support request moves between agents (manager → billing /
technical / account → back to manager → response / escalation), not the
business rules that decide *where* it moves (see `backend/policy/`) nor the
agent capabilities themselves (see `backend/agents/`).

## TODO

- [ ] Define the shared graph state schema (conversation/ticket context, routing decisions, history)
- [ ] Define graph nodes wrapping each agent in `backend/agents/`
- [ ] Define conditional routing edges, delegating routing decisions to `backend/policy/`
- [ ] Configure checkpointing/persistence (e.g. backed by Postgres/Redis)
- [ ] Define human-in-the-loop interrupt points for escalation
