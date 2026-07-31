"""Shared fixtures for supervisor API tests.

No test database exists (see `tests/unit/core/test_rate_limit.py`), so these
fixtures fake exactly two things: the DB session `get_current_user` uses to
resolve a bearer token into a `User` (real JWTs, minted via
`create_access_token`, are still decoded for real -- only the user lookup is
faked), and the session `backend/api/supervisor.py`'s routes open (its
`ApprovalRequestRepository` calls are monkeypatched per test instead).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from backend.auth.jwt import create_access_token
from backend.database.enums import ApprovalStatus, TicketPriority, TicketStatus, UserRole
from backend.database.models.approval_request import ApprovalRequest
from backend.database.models.ticket import Ticket
from backend.database.models.user import User


class _FakeAsyncSessionCM:
    """Stands in for the object `async_session_factory()` returns."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def __aenter__(self) -> Any:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _UserLookupSession:
    """Fakes the one thing `get_current_user` needs: `await session.get(User, id)`."""

    def __init__(self, user: User) -> None:
        self._user = user

    async def get(self, _model: type, id_: uuid.UUID) -> User | None:
        return self._user if id_ == self._user.id else None


class _NoOpSession:
    """A session double for routes whose repository calls are monkeypatched
    directly, so the session itself only needs to survive `async with`/`commit()`."""

    async def __aenter__(self) -> _NoOpSession:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def commit(self) -> None:
        pass


@pytest.fixture
def issue_token(monkeypatch: pytest.MonkeyPatch):
    """Returns `issue_token(role)` -> bearer token, wiring `get_current_user`'s
    DB lookup to resolve it to a matching fake `User` (no real database)."""

    def _issue(role: UserRole) -> str:
        user = User(
            id=uuid.uuid4(),
            email=f"{role.value}@example.com",
            password_hash="unused",
            full_name=f"Test {role.value.title()}",
            role=role,
            is_active=True,
        )
        monkeypatch.setattr(
            "backend.auth.dependencies.async_session_factory",
            lambda: _FakeAsyncSessionCM(_UserLookupSession(user)),
        )
        return create_access_token(user_id=user.id, role=role)

    return _issue


@pytest.fixture(autouse=True)
def _supervisor_route_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every supervisor-API test gets a no-op session for the route's own
    `async with async_session_factory()`; tests control repository behavior
    by monkeypatching `ApprovalRequestRepository` methods directly.

    Also no-ops `log_audit_event` by default: unmocked, it attempts a real
    (unreachable, ~2-3s-to-fail) Postgres connection on every call -- fine
    for the odd test, ruinous for `test_rate_limit.py`'s dozens of calls per
    test. `audit_events` (below) overrides this with a capturing version for
    tests that need to assert on what was logged.
    """
    monkeypatch.setattr("backend.api.supervisor.async_session_factory", lambda: _NoOpSession())

    async def _noop_log_audit_event(**_kwargs: Any) -> None:
        pass

    monkeypatch.setattr("backend.api.supervisor.log_audit_event", _noop_log_audit_event)


@pytest.fixture
def audit_events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captures every `log_audit_event(...)` call the supervisor routes make,
    without touching a real database."""
    calls: list[dict[str, Any]] = []

    async def _fake_log_audit_event(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("backend.api.supervisor.log_audit_event", _fake_log_audit_event)
    return calls


def build_approval_request(
    *,
    ticket_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    priority: TicketPriority = TicketPriority.HIGH,
    status: ApprovalStatus = ApprovalStatus.PENDING,
    selected_agent: str = "billing_agent",
    matched_policy_rules: tuple[str, ...] = ("refund",),
    draft_response: str = "Draft response awaiting review.",
    retrieved_context: str | None = "Some retrieved context.",
    comments: str | None = None,
    approved_by: uuid.UUID | None = None,
    decided_at: datetime | None = None,
) -> ApprovalRequest:
    """Build an in-memory `ApprovalRequest` (with its `ticket` relationship
    already attached) -- no database session involved, same trick as
    `tests/unit/database/repositories/test_knowledge_article.py`."""
    ticket_id = ticket_id or uuid.uuid4()
    customer_id = customer_id or uuid.uuid4()
    ticket = Ticket(
        id=ticket_id,
        customer_id=customer_id,
        subject="Test ticket",
        description="Test ticket description.",
        priority=priority,
        status=TicketStatus.APPROVAL_REQUIRED,
    )
    approval_request = ApprovalRequest(
        id=uuid.uuid4(),
        ticket_id=ticket_id,
        status=status,
        selected_agent=selected_agent,
        matched_policy_rules=list(matched_policy_rules),
        draft_response=draft_response,
        retrieved_context=retrieved_context,
        comments=comments,
        approved_by=approved_by,
        decided_at=decided_at,
        requested_at=datetime.now(UTC),
    )
    approval_request.ticket = ticket
    return approval_request
