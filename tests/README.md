# tests/

Test suite for SupportOps AI. 167 tests total.

- `unit/` — fast, isolated tests with no external dependencies (mirrors
  `backend/` structure). 159 tests; no real Postgres/Redis anywhere -- both
  are either mocked directly or stood in for with `fakeredis`/hand-rolled
  async session doubles (see individual test-module docstrings).
- `integration/` — tests exercising a real Redis and/or a real Postgres
  (`docker compose up -d redis postgres`). 8 tests across three files, each
  a regression test for a bug a mocked unit test couldn't have caught (a
  cross-event-loop `redis.asyncio`/asyncpg failure, and a model/schema
  drift) -- see `tests/integration/README.md`. Every test skips itself
  (rather than failing) if the service it needs isn't reachable, which is
  what happens in CI today (see `.github/workflows/*.yml`).
- `fixtures/` — intended for shared pytest fixtures/factories; still unused
  in practice (see `tests/fixtures/README.md` for what happened instead).
- `conftest.py` — the one repo-wide shared fixture: `client` (a `TestClient`
  for `backend.main.app`). Directory-scoped fixtures (e.g. `issue_token`,
  `build_approval_request` in `tests/unit/api/conftest.py`;
  `real_redis`/`real_postgres`/`real_customer` in
  `tests/integration/conftest.py`) live next to the tests that need them
  rather than in `fixtures/`.

## Conventions

- A new module under `backend/x/y.py` gets unit tests under `tests/unit/x/test_y.py`.
- Integration tests are marked `@pytest.mark.integration` (registered in
  `pyproject.toml`) so they *can* be filtered out of a fast run
  (`pytest -m "not integration"`), though their self-skipping behavior
  means that's a convenience, not a requirement for a plain `pytest` to
  stay green without real infrastructure.
- Prefer a directory-scoped `conftest.py` for fixtures/builders shared by
  more than one test module in that directory (e.g.
  `tests/unit/api/conftest.py`) over adding to `tests/fixtures/`, which
  hasn't ended up hosting anything -- see that directory's README.

## TODO

- [x] Add `conftest.py` with a shared fixture (`client`); a shared DB-session
      fixture never materialized since no test database exists yet -- each
      unit-test module fakes what it needs instead
- [x] Add integration test harness -- `tests/integration/conftest.py`'s
      `real_redis`/`real_postgres` fixtures, against the existing
      `docker-compose.yml` services (no testcontainers needed)
- [ ] Configure coverage thresholds in CI
