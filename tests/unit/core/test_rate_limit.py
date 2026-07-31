"""Unit tests for the shared API rate limiting configuration.

Exercises throttling end-to-end via `/supervisor/queue/{id}/reject` and
`/auth/login` -- the former authenticated with real supervisor JWTs (with
the DB user-lookup and the approval-request repository faked, no test
database exists yet), the latter only checked for *wiring* (that it does
get throttled) since it needs a real database connection to reach a normal
response and no test-database fixture exists yet.

Storage/limit note: `backend.core.rate_limit.limiter` is Redis-backed
(`storage_uri=settings.redis_url`), but no Redis is reachable in this
environment (nor is one provisioned in CI -- see `.github/workflows/ci.yml`),
so every test here exercises the limiter's `in_memory_fallback` path, not
genuine distributed counting. That path enforces `_REDIS_OUTAGE_FALLBACK_LIMIT`
-- a single blanket ceiling shared by every route while the fallback is
active -- rather than each route's own configured limit (`_LOGIN_RATE_LIMIT`,
`_APPROVAL_DECISION_RATE_LIMIT`, ...); see that module's docstring for why.
So these tests verify *that* the fallback activates and throttles correctly
(counter increments, per-key isolation, eventual 429), not the exact
per-route limit values, which can only be verified against a reachable
Redis. `limits`' Redis storage backend is implemented entirely via Lua
scripts (`EVALSHA`), which `fakeredis` does not support, so substituting it
for these tests isn't viable either.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import create_access_token
from backend.core.rate_limit import limiter
from backend.database.enums import UserRole
from backend.database.models.user import User
from backend.database.repositories.approval_request import ApprovalRequestRepository
from backend.main import app
from tests.unit.api.conftest import build_approval_request

_KNOWN_TICKET_ID = "00000000-0000-0000-0000-000000000001"

# Mirrors backend.core.rate_limit._REDIS_OUTAGE_FALLBACK_LIMIT. Hardcoded
# rather than imported so a change to that constant fails this test rather
# than silently changing what it verifies.
_FALLBACK_LIMIT_PER_MINUTE = 20


@pytest.fixture(autouse=True)
def _reset_limiter_storage() -> Iterator[None]:
    """Each test gets a fresh rate-limit window regardless of run order.

    `Limiter.reset()` isn't fallback-aware (it only catches
    `NotImplementedError`, not connection errors -- see
    `backend/core/rate_limit.py`), so it raises against the primary
    (unreachable) Redis storage even though actual rate-limit *checks*
    degrade gracefully. Swallow that here; it's a test-fixture concern, not
    a production code path.
    """
    try:
        limiter.reset()
    except Exception:
        pass
    yield
    try:
        limiter.reset()
    except Exception:
        pass


class _NoOpSession:
    async def __aenter__(self) -> _NoOpSession:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def commit(self) -> None:
        pass


@pytest.fixture
def supervisor_auth_headers(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Returns `issue()` -> bearer-token headers for a *new* supervisor each
    call, with the DB user-lookup and the approval-request repository faked
    so `/supervisor/...` is reachable without a database, purely to exercise
    rate limiting. Each call registers its user so multiple concurrently
    "logged in" supervisors can be authenticated within one test (see
    `test_different_users_get_independent_rate_limit_counters`)."""
    known_users: dict[uuid.UUID, User] = {}

    class _UserLookupSession:
        async def __aenter__(self) -> _UserLookupSession:
            return self

        async def __aexit__(self, *exc_info: object) -> bool:
            return False

        async def get(self, _model: type, id_: uuid.UUID) -> User | None:
            return known_users.get(id_)

    monkeypatch.setattr("backend.auth.dependencies.async_session_factory", _UserLookupSession)
    monkeypatch.setattr("backend.api.supervisor.async_session_factory", _NoOpSession)

    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))

    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID) -> Any:
        return item

    async def fake_decide(self: ApprovalRequestRepository, **kwargs: Any) -> Any:
        return item

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)
    monkeypatch.setattr(ApprovalRequestRepository, "decide", fake_decide)

    # Unmocked, log_audit_event attempts a real (unreachable, ~2-3s-to-fail)
    # Postgres connection on every call -- fine once, ruinous across the
    # dozens of reject calls these tests make.
    async def _noop_log_audit_event(**_kwargs: Any) -> None:
        pass

    monkeypatch.setattr("backend.api.supervisor.log_audit_event", _noop_log_audit_event)

    def _issue() -> dict[str, str]:
        user = User(
            id=uuid.uuid4(),
            email=f"supervisor-{uuid.uuid4()}@example.com",
            password_hash="unused",
            full_name="Test Supervisor",
            role=UserRole.SUPERVISOR,
            is_active=True,
        )
        known_users[user.id] = user
        token = create_access_token(user_id=user.id, role=UserRole.SUPERVISOR)
        return {"Authorization": f"Bearer {token}"}

    return _issue


def test_requests_within_limit_are_not_throttled(
    client: TestClient, supervisor_auth_headers: Any
) -> None:
    headers = supervisor_auth_headers()
    for _ in range(_FALLBACK_LIMIT_PER_MINUTE):
        response = client.post(
            f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject", json={}, headers=headers
        )
        assert response.status_code == 200


def test_requests_over_limit_return_429(client: TestClient, supervisor_auth_headers: Any) -> None:
    headers = supervisor_auth_headers()
    for _ in range(_FALLBACK_LIMIT_PER_MINUTE):
        client.post(f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject", json={}, headers=headers)

    response = client.post(f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject", json={}, headers=headers)

    assert response.status_code == 429
    assert "error" in response.json()


def test_different_users_get_independent_rate_limit_counters(
    client: TestClient, supervisor_auth_headers: Any
) -> None:
    """Rate-limit keys are per-authenticated-user (`resolve_rate_limit_key`),
    so one user hitting their limit must not throttle a different user."""
    exhausted_user_headers = supervisor_auth_headers()
    for _ in range(_FALLBACK_LIMIT_PER_MINUTE):
        client.post(
            f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject",
            json={},
            headers=exhausted_user_headers,
        )
    throttled_response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject", json={}, headers=exhausted_user_headers
    )
    assert throttled_response.status_code == 429

    fresh_user_headers = supervisor_auth_headers()
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject", json={}, headers=fresh_user_headers
    )
    assert response.status_code == 200


def test_login_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    # No test database is configured in this environment, so calls within
    # the limit can't reach a normal response. Fail fast at the session
    # factory instead of letting each attempt hang on a real (refused) DB
    # connection -- irrelevant here, since this only checks that the route
    # is throttled after enough attempts, not that login itself succeeds.
    def _unavailable_session_factory() -> None:
        raise RuntimeError("no database configured for this test")

    monkeypatch.setattr("backend.auth.router.async_session_factory", _unavailable_session_factory)

    local_client = TestClient(app, raise_server_exceptions=False)
    credentials = {"username": "someone@example.com", "password": "wrong"}

    for _ in range(_FALLBACK_LIMIT_PER_MINUTE):
        local_client.post("/auth/login", data=credentials)

    response = local_client.post("/auth/login", data=credentials)

    assert response.status_code == 429
    assert "error" in response.json()
