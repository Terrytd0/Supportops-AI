# backend/schemas/

Pydantic schemas defining data contracts at system boundaries: API request and
response models, and internal contracts passed between services/agents/graph.
ORM models from `backend/database/models/` must never be returned directly
from API routes — always map to a schema here.

## TODO

- [ ] Define request/response schemas per API resource (mirroring `backend/api/routes/`)
- [ ] Define shared graph/agent state schemas used by `backend/graph/`
