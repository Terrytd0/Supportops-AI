"""Unit tests for the shared API rate limiting configuration.

Exercises throttling end-to-end via the DB-free supervisor placeholder
endpoints (30/minute/IP). `/auth/login` is only checked for *wiring* --
that it does get throttled -- since it requires a real database connection
to reach a normal response and no test-database fixture exists yet.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.core.rate_limit import limiter
from backend.main import app

_KNOWN_TICKET_ID = "00000000-0000-0000-0000-000000000001"

# Mirrors the limits set in backend/auth/router.py and backend/api/supervisor.py
# (Sprint 4 Day 5 Task 3). Hardcoded rather than imported so a change to those
# limits fails this test rather than silently changing what it verifies.
_LOGIN_LIMIT_PER_MINUTE = 5
_APPROVAL_DECISION_LIMIT_PER_MINUTE = 30


@pytest.fixture(autouse=True)
def _reset_limiter_storage() -> Iterator[None]:
    """Each test gets a fresh rate-limit window regardless of run order."""
    limiter.reset()
    yield
    limiter.reset()


def test_requests_within_limit_are_not_throttled(client: TestClient) -> None:
    for _ in range(_APPROVAL_DECISION_LIMIT_PER_MINUTE):
        response = client.post(f"/supervisor/{_KNOWN_TICKET_ID}/reject", json={})
        assert response.status_code == 200


def test_requests_over_limit_return_429(client: TestClient) -> None:
    for _ in range(_APPROVAL_DECISION_LIMIT_PER_MINUTE):
        client.post(f"/supervisor/{_KNOWN_TICKET_ID}/reject", json={})

    response = client.post(f"/supervisor/{_KNOWN_TICKET_ID}/reject", json={})

    assert response.status_code == 429
    assert "error" in response.json()


def test_login_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    # No test database is configured in this environment, so calls within
    # the limit can't reach a normal response. Fail fast at the session
    # factory instead of letting each attempt hang on a real (refused) DB
    # connection -- irrelevant here, since this only checks that the route
    # is throttled after enough attempts, not that login itself succeeds.
    def _unavailable_session_factory() -> None:
        raise RuntimeError("no database configured for this test")

    monkeypatch.setattr(
        "backend.auth.router.async_session_factory", _unavailable_session_factory
    )

    local_client = TestClient(app, raise_server_exceptions=False)
    credentials = {"username": "someone@example.com", "password": "wrong"}

    for _ in range(_LOGIN_LIMIT_PER_MINUTE):
        local_client.post("/auth/login", data=credentials)

    response = local_client.post("/auth/login", data=credentials)

    assert response.status_code == 429
    assert "error" in response.json()
