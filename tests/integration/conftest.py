"""Shared fixtures for tests/integration/.

Unlike tests/unit/, these tests deliberately do *not* monkeypatch
`get_redis_client` -- the whole point is to exercise the real
`redis.asyncio.Redis` client against a real Redis server (see
`tests/integration/test_ticket_workflow.py`). `real_redis` points
`backend.core.redis_client`'s settings at `localhost` (the default `.env`
points at the docker-compose-internal hostname `redis`, unreachable from a
test process running on the host) and skips the test outright if nothing is
listening there, rather than failing -- see `tests/integration/README.md`:
these tests exercise real infrastructure that may not be running.

`client`/`issue_token` mirror `tests/unit/api/conftest.py`'s fixtures of the
same name (real JWTs, a faked DB-backed user lookup) -- duplicated rather
than imported since unit and integration fixtures are deliberately kept
independent (integration tests should not depend on unit-test scaffolding).
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.auth.jwt import create_access_token
from backend.config.settings import Settings
from backend.database.enums import CustomerTier, UserRole
from backend.database.models.approval_request import ApprovalRequest
from backend.database.models.audit_log import AuditLog
from backend.database.models.customer import Customer
from backend.database.models.ticket import Ticket
from backend.database.models.user import User
from backend.database.session import async_session_factory
from backend.main import app

_REAL_REDIS_HOST = "localhost"
_REAL_REDIS_PORT = 6379
_REAL_POSTGRES_HOST = "localhost"
_REAL_POSTGRES_PORT = 5432


def _is_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture
def real_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `backend.core.redis_client.get_redis_client` at a real, local
    Redis, skipping the test if one isn't reachable (e.g. `docker compose up
    redis` hasn't been run) rather than failing it."""
    if not _is_reachable(_REAL_REDIS_HOST, _REAL_REDIS_PORT):
        pytest.skip(
            f"real Redis not reachable at {_REAL_REDIS_HOST}:{_REAL_REDIS_PORT} "
            "-- start it with `docker compose up -d redis` to run this test"
        )

    test_settings = Settings(
        redis_url=f"redis://{_REAL_REDIS_HOST}:{_REAL_REDIS_PORT}/0",
        redis_connect_timeout_seconds=2.0,
    )
    monkeypatch.setattr("backend.core.redis_client.get_settings", lambda: test_settings)


@pytest.fixture
def real_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `backend.database.session.async_session_factory` at a real,
    local Postgres, skipping the test if one isn't reachable (e.g. `docker
    compose up postgres` hasn't been run) rather than failing it. The
    default `.env` points `DATABASE_URL` at the docker-compose-internal
    hostname `postgres`, unreachable from a test process running on the
    host -- same reasoning as `real_redis` above."""
    if not _is_reachable(_REAL_POSTGRES_HOST, _REAL_POSTGRES_PORT):
        pytest.skip(
            f"real Postgres not reachable at {_REAL_POSTGRES_HOST}:{_REAL_POSTGRES_PORT} "
            "-- start it with `docker compose up -d postgres` to run this test"
        )

    test_settings = Settings(
        database_url=(
            f"postgresql+asyncpg://supportops:supportops@"
            f"{_REAL_POSTGRES_HOST}:{_REAL_POSTGRES_PORT}/supportops_ai"
        )
    )
    monkeypatch.setattr("backend.database.session.get_settings", lambda: test_settings)


@pytest.fixture
def real_customer(real_postgres: None) -> Generator[uuid.UUID]:
    """Insert a real, throwaway `Customer` row for the test to reference as
    `customer_id`, and remove it (and anything created against it -- tickets,
    approval requests, audit logs, all `ON DELETE RESTRICT`) afterward.

    Runs its setup/teardown in their own one-shot `asyncio.run()` loops --
    distinct from the app's own loops, but safe: `async_session_factory` is
    loop-scoped (`backend/database/session.py`) precisely so any loop can
    use it correctly, including a short-lived one like this.
    """
    customer_id = uuid.uuid4()

    async def _create() -> None:
        async with async_session_factory() as session:
            session.add(
                Customer(
                    id=customer_id,
                    name="Integration Test Customer",
                    email=f"integration-test-{customer_id}@example.com",
                    tier=CustomerTier.STANDARD,
                )
            )
            await session.commit()

    asyncio.run(_create())

    yield customer_id

    async def _cleanup() -> None:
        async with async_session_factory() as session:
            ticket_ids_stmt = select(Ticket.id).where(Ticket.customer_id == customer_id)
            ticket_ids = (await session.execute(ticket_ids_stmt)).scalars().all()
            if ticket_ids:
                await session.execute(delete(AuditLog).where(AuditLog.ticket_id.in_(ticket_ids)))
                await session.execute(
                    delete(ApprovalRequest).where(ApprovalRequest.ticket_id.in_(ticket_ids))
                )
                await session.execute(delete(Ticket).where(Ticket.id.in_(ticket_ids)))
            await session.execute(delete(Customer).where(Customer.id == customer_id))
            await session.commit()

    asyncio.run(_cleanup())


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class _FakeAsyncSessionCM:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _UserLookupSession:
    def __init__(self, user: User) -> None:
        self._user = user

    async def get(self, _model: type, id_: uuid.UUID) -> User | None:
        return self._user if id_ == self._user.id else None


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
