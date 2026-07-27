# backend/api/

FastAPI HTTP layer. Contains only HTTP concerns (request/response handling,
routing, dependency injection, middleware) — no business logic.

- `routes/` — one module per resource/domain, each exporting an `APIRouter`.
- `dependencies/` — FastAPI `Depends`-compatible callables (auth, db sessions, pagination, etc).
- `middleware/` — ASGI middleware (request logging, correlation IDs, error handling, etc).

## Conventions

- Routes call into `backend/services/`; they must not call repositories or
  agents directly.
- All request/response bodies must be typed with schemas from `backend/schemas/`.

## TODO

- [ ] Add versioning strategy for routes (e.g. `/api/v1/...`)
- [ ] Add global exception handlers (validation errors, domain errors, auth errors)
- [ ] Add request/response logging middleware with correlation IDs
