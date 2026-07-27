# backend/policy/

Business rules governing agent routing, escalation, and guardrails. Kept
separate from `backend/graph/` (control flow) and `backend/agents/`
(capability) so business rules can change without touching orchestration
mechanics.

## TODO

- [ ] Routing policy: map request classification → responsible agent
- [ ] Escalation policy: conditions under which a conversation is handed to a human
- [ ] Guardrails: content/safety checks applied to agent inputs/outputs
- [ ] SLA-driven policy (e.g., time-based auto-escalation)
