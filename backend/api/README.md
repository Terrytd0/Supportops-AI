# backend/api/

FastAPI HTTP layer. Contains only HTTP concerns (request/response handling,
routing, dependency injection, middleware) — no business logic.

- `routes/` — one module per resource/domain, each exporting an `APIRouter`.
  `routes/tickets.py` (`POST /tickets`) is the reference example of the
  convention below: it calls `backend.services.ticket.create_ticket`, never
  a repository or `async_session_factory` directly.
- `dependencies/` — FastAPI `Depends`-compatible callables (auth, db sessions, pagination, etc).
- `middleware/` — ASGI middleware (request logging, correlation IDs, error handling, etc).

## Conventions

- Routes call into `backend/services/`; they must not call repositories or
  agents directly.
- All request/response bodies must be typed with schemas from `backend/schemas/`.

**Current exception:** `auth/router.py`, `supervisor.py`, and
`routes/customers.py` all call repositories/`async_session_factory` directly
-- there's no service layer yet for any of these resources (`customers.py`
is a single read-only lookup, arguably too thin to warrant one). Not a new
violation, just an acknowledged, pre-existing gap; `routes/tickets.py` (via
`backend.services.ticket`) is the pattern to follow instead -- see
`backend/services/README.md`'s TODO.

- `routes/customers.py` (`GET /customers`) lists seeded customers so a
  caller can find a valid `customer_id` for `POST /tickets` -- see that
  route's docstring and `backend.services.ticket.CustomerNotFound`.

## TODO

- [ ] Add versioning strategy for routes (e.g. `/api/v1/...`)
- [ ] Add global exception handlers (validation errors, domain errors, auth errors)
- [ ] Add request/response logging middleware with correlation IDs
