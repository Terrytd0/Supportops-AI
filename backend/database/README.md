# backend/database/

Persistence layer.

- `models/` — SQLAlchemy declarative models (ORM layer only, no business logic).
- `migrations/` — Alembic migration environment and version scripts.
- `repositories/` — Repository pattern: all query logic lives here; services
  depend on repositories, never on raw SQLAlchemy sessions directly.
- `session.py` — `async_session_factory()`. Loop-scoped, not one process-wide
  engine: an `AsyncEngine`'s connection pool holds asyncpg connections bound
  to whichever event loop first uses them, and this app runs two long-lived
  ones (FastAPI's own request loop, and `backend.core.asyncio_utils.run_sync`'s
  background loop, used by `backend.graph.nodes._enqueue_supervisor_review`
  and the knowledge-base tool's search). Sharing one engine across both used
  to crash `pool_pre_ping`'s per-checkout health check with a `RuntimeError`
  that poisoned a pooled connection for every future checkout that landed on
  it -- see the module docstring and `tests/integration/test_idempotency_cross_loop.py`.

`docs/database_schema.md` documents every table, including `knowledge_articles`
(`KnowledgeArticle`/`KnowledgeArticleRepository`, backing
`backend.tools.knowledge_base.KnowledgeBaseSearchTool`) and the extended
`approval_requests` (`ApprovalRequest` also carries `draft_response`,
`retrieved_context`, `selected_agent`, `matched_policy_rules` -- it *is* the
supervisor queue, see `backend/api/README.md`) -- both added to the models
mid-sprint, and for a time without a matching Alembic migration (see
`backend/database/migrations/README.md`'s cautionary tale and
`tests/integration/test_schema_migrations.py`, which now guards against a
repeat).

## TODO

- [x] Add async engine/session factory and declarative base (`base.py`, `session.py`)
- [x] Define domain models per `docs/database_schema.md` (`models/`)
- [x] Define repository interfaces for `KnowledgeArticle`, `ApprovalRequest`, `AuditLog`
- [x] Define a `TicketRepository` (`backend.services.ticket.create_ticket`,
      `POST /tickets`, is its first caller) -- `ApprovalRequestRepository`'s
      `ticket_id` foreign key now has a real row to reference
- [x] Generate the first Alembic revision(s) (`alembic revision --autogenerate`)
      -- see `backend/database/migrations/README.md`; three exist now,
      covering every model
- [ ] Add a FastAPI dependency yielding a request-scoped `AsyncSession`
- [x] Define a `CustomerRepository` (read-only: `get_by_id`, `list_all`) --
      `backend.services.ticket._execute` uses `get_by_id` to validate
      `customer_id` before inserting a `Ticket`, and `list_all` backs
      `GET /customers`
