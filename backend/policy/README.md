# backend/policy/

Business rules governing agent routing, escalation, and guardrails. Kept
separate from `backend/graph/` (control flow) and `backend/agents/`
(capability) so business rules can change without touching orchestration
mechanics.

## `rules.py` — `evaluate_policy`

The only component that decides `requires_human_review`. Deterministic and
model-free: every rule is a keyword match, a dollar-amount regex, a
threshold comparison, or a boolean already decided upstream --
`agent_unresolved`, the specialist agent's own structured "I couldn't
confidently resolve this" signal (`backend.agents.base.AgentResult
.unresolved`, threaded through `backend.graph.nodes.execute_agent_node` and
`confidence_evaluation_node`). Agents report an outcome; only this function
turns it into an escalation decision -- see `backend/agents/README.md`.

Current rules: `legal`/`lawsuit`/`attorney`/`security`/`breach`/`fraud`,
`refund` (+ `refund_over_threshold`), `low_confidence`, `agent_unresolved`.

## TODO

- [ ] Routing policy: map request classification → responsible agent
- [ ] Guardrails: content/safety checks applied to agent inputs/outputs
- [ ] SLA-driven policy (e.g., time-based auto-escalation)
- [ ] Source per-tenant policy thresholds (e.g. the refund amount
      threshold) from a repository/config table instead of module constants
