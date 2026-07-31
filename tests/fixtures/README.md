# tests/fixtures/

Intended for shared test fixtures, factories, and sample data used across
unit and integration tests -- still unused in practice, even though the
database models this was waiting on now exist (`Ticket`, `User`,
`ApprovalRequest`, `KnowledgeArticle`, ...).

What happened instead: builder functions for the few models tests need
in-memory (e.g. `build_approval_request` in
`tests/unit/api/conftest.py`, constructing a `Ticket` + `ApprovalRequest`
directly without a session) live next to the tests that use them, since
so far only one or two test modules ever need each one. A `factory_boy`
dependency and a shared `tests/fixtures/` module would be reasonable if a
third or fourth consumer shows up -- see `tests/README.md`'s "Conventions".

## TODO

- [ ] Revisit once model-construction helpers are needed by three or more
      test modules -- until then, per-directory `conftest.py` builder
      functions (see `tests/unit/api/conftest.py`) are simpler
- [ ] Add sample support-conversation fixtures for agent/graph testing, if
      a need for them beyond each test module's own inline fixtures emerges
