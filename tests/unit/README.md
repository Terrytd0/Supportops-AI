# tests/unit/

Fast, isolated unit tests. No network, database, or Redis dependencies —
mock/stub collaborators. Directory structure mirrors `backend/`:

`agents/`, `api/` (incl. `conftest.py`'s shared JWT/session doubles),
`auth/`, `core/`, `database/repositories/`, `graph/`, `policy/`,
`services/`, `tools/`, plus `test_main.py` at the top level.

159 tests total. Every OpenAI/CrewAI call is mocked at the SDK boundary
(never asserting on exact LLM wording); every Redis-backed feature is
tested against `fakeredis` or a raising double (never a real connection);
Postgres access is tested against monkeypatched repository methods or
in-memory-constructed ORM objects (never a real session).

## TODO

- [ ] Add unit tests as each `backend/` module gains an implementation.
