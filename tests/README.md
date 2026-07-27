# tests/

Test suite for SupportOps AI.

- `unit/` — fast, isolated tests with no external dependencies (mirrors `backend/` structure).
- `integration/` — tests exercising real Postgres/Redis (e.g. via testcontainers or docker compose).
- `fixtures/` — shared pytest fixtures and test data/factories.

## Conventions

- A new module under `backend/x/y.py` gets unit tests under `tests/unit/x/test_y.py`.
- Integration tests should be marked (e.g. `@pytest.mark.integration`) so they
  can be excluded from fast local runs.

## TODO

- [ ] Add `conftest.py` with shared fixtures (test client, db session, settings override)
- [ ] Add integration test harness (docker compose test stack or testcontainers)
- [ ] Configure coverage thresholds in CI
