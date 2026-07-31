# backend/schemas/

Pydantic schemas defining data contracts at system boundaries: API request and
response models, and internal contracts passed between services/agents/graph.
ORM models from `backend/database/models/` must never be returned directly
from API routes — always map to a schema here.

- `auth.py` — `Token`, `AuthenticatedUser` (`backend/auth/router.py`).
- `supervisor.py` — `SupervisorQueueItem`/`SupervisorQueueResponse`,
  `ApprovalDecisionRequest`, `EditDraftRequest` (`backend/api/supervisor.py`).
  `selected_agent`/`category`-shaped fields are plain `str`, not
  `backend.graph.state`'s enums, so this layer doesn't couple to the graph
  layer's specific vocabulary types.
- `ticket.py` — `TicketCreateRequest`/`TicketCreateResponse`
  (`backend/api/routes/tickets.py`), following the same plain-`str` convention.
- `customer.py` — `CustomerResponse`/`CustomerListResponse`
  (`backend/api/routes/customers.py`, `GET /customers`).

## TODO

- [ ] Define shared graph/agent state schemas used by `backend/graph/`, if
      a need for them (beyond the TypedDict `WorkflowState` already provides)
      materializes
