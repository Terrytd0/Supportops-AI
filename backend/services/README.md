# backend/services/

Application/business services. This is the layer `backend/api/routes/`
depends on — it orchestrates repositories (`backend/database/repositories/`),
the agent graph (`backend/graph/`), and policy (`backend/policy/`) to fulfill
a use case. Routes must not bypass this layer to talk to the database or
agents directly.

## `audit.py` — `log_audit_event`

The one call site every action-recording caller uses
(`backend/api/supervisor.py`'s view/approve/edit/reject,
`backend.graph.nodes.persist_results_node`'s "AI draft created"). Async, and
persists a real `AuditLog` row via `AuditLogRepository` -- best-effort: a
failed write is logged as a warning, never raised, so a missing audit row
never crashes the caller (the structured log line is always emitted
regardless).

## `idempotency.py` — `IdempotencyStore`

Redis-backed at-most-once execution for `POST /tickets`'s `Idempotency-Key`.
The one Redis-backed feature in this codebase that fails *closed*, not open
-- see the module docstring. `ticket.py` (below) is its only caller.

## `ticket.py` — `create_ticket`

The first real example of this package's intended pattern: `backend/api/
routes/tickets.py` calls this, not repositories/`async_session_factory`
directly (unlike `backend/api/supervisor.py`, which still takes the
shortcut `backend/api/README.md` documents as a known, pre-existing gap).
Orchestrates `IdempotencyStore` (Redis), `TicketRepository` (Postgres, the
system of record), and `backend.graph.workflow.get_graph()` (unmodified) in
one place.

Before inserting, `_execute` checks `payload.customer_id` against
`CustomerRepository.get_by_id` and raises `CustomerNotFound` if it doesn't
exist (also raised, as defense in depth, if the insert itself still hits an
`IntegrityError` -- e.g. a customer removed in a race with the check). The
route (`backend/api/routes/tickets.py`) translates this to a 404; without it,
a nonexistent `customer_id` used to surface as a raw PostgreSQL
foreign-key-violation 500. `GET /customers` (`backend/api/routes/
customers.py`) is how a caller finds a real `customer_id` to use.

## TODO

- [ ] Define a `SupervisorService` (or similar) so `backend/api/supervisor.py`
      stops calling `ApprovalRequestRepository`/`async_session_factory`
      directly -- see `backend/api/README.md`'s "Current exception"; `ticket.py`
      is the pattern to follow
- [ ] Define transaction boundaries (a service call = one unit of work)
