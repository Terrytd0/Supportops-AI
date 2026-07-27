# backend/services/

Application/business services. This is the layer `backend/api/routes/`
depends on — it orchestrates repositories (`backend/database/repositories/`),
the agent graph (`backend/graph/`), and policy (`backend/policy/`) to fulfill
a use case. Routes must not bypass this layer to talk to the database or
agents directly.

## TODO

- [ ] Define service interfaces for core use cases (create ticket, post message,
      request agent resolution, escalate to human)
- [ ] Define transaction boundaries (a service call = one unit of work)
