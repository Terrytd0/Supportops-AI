# backend/agents/

Domain-specific agent implementations, one package per agent:

- `billing/` — handles billing, invoicing, and payment-related support requests.
- `technical/` — handles technical/product troubleshooting requests.
- `account/` — handles account management requests (profile, access, settings).
- `manager/` — supervisor agent: triages incoming requests, routes to the
  appropriate domain agent, and handles escalation/hand-off to a human.

## Conventions

- Agents define *capability* (what an agent can do and which tools it uses).
  Control flow between agents belongs in `backend/graph/`; business rules
  governing routing/escalation belong in `backend/policy/`.
- Agents should consume tools from `backend/tools/`, not implement raw
  integrations inline.

## TODO

- [ ] Define a common agent interface/base class shared across domain agents
- [ ] Implement billing agent (CrewAI role/task definition)
- [ ] Implement technical agent (CrewAI role/task definition)
- [ ] Implement account agent (CrewAI role/task definition)
- [ ] Implement manager/supervisor agent and its routing contract with `backend/graph/`
