# tests/integration/

Integration tests exercising real Postgres/Redis dependencies. Mark tests with
`@pytest.mark.integration` (registered in `pyproject.toml`) so they're easy
to filter out of a fast run (`pytest -m "not integration"`) -- though as
written today they're already safe to leave in a plain `pytest` run: the
`real_redis`/`real_postgres` fixtures (`conftest.py`) skip a test outright if
nothing is listening on `localhost:6379`/`localhost:5432` rather than
failing it (this is what happens in CI today -- neither service is
provisioned there, see `.github/workflows/*.yml`).

- `test_ticket_workflow.py` -- real Redis only; fakes Postgres access
  (matching `tests/unit/services/test_ticket.py`'s conventions). A
  regression test for `run_sync`/`get_redis_client` sharing a loop-affine
  connection across two different event loops (see
  `backend/core/asyncio_utils.py`'s module docstring) -- exactly the kind of
  thing a fake/in-memory Redis (`fakeredis`) doesn't reproduce.
- `test_idempotency_cross_loop.py` -- both real Redis *and* real Postgres
  (`real_customer` inserts/tears down a throwaway `Customer` row). A
  regression test for the same class of bug on the Postgres side:
  `backend/database/session.py`'s engine/session factory sharing a
  loop-affine asyncpg connection across the same two event loops, which
  intermittently 500'd `POST /tickets` regardless of whether an
  `Idempotency-Key` was supplied (see that module's docstring).
- `test_schema_migrations.py` -- real Postgres; asserts (via
  `alembic.autogenerate.compare_metadata`, the same diff engine `alembic
  revision --autogenerate` and `alembic check` use) that every
  `backend/database/models/` model has a matching column in the live
  schema. A regression test for `knowledge_articles` and
  `approval_requests`'s AI-execution-context columns having been added to
  the models without ever generating a migration -- see
  `backend/database/migrations/README.md`.

## TODO

- [ ] Add real repository integration tests against the now-available real
      Postgres (`KnowledgeArticleRepository`, `ApprovalRequestRepository`,
      `AuditLogRepository`, `TicketRepository`, `CustomerRepository`) --
      every test of them still mocks the session rather than hitting a real
      Postgres
- [ ] Extend `test_ticket_workflow.py` to use `real_postgres`/`real_customer`
      too, rather than faking `CustomerRepository`/`TicketRepository`
