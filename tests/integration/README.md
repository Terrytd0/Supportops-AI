# tests/integration/

Integration tests exercising real Postgres/Redis dependencies. Mark tests with
`@pytest.mark.integration` so they can be excluded from fast local/unit runs.

## TODO

- [ ] Add integration test harness (docker compose test stack or testcontainers)
- [ ] Add database repository integration tests once repositories exist
- [ ] Add end-to-end API tests exercising the full agent graph once implemented
