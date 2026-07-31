"""Tests for `GET /customers`.

`backend.api.routes.customers.CustomerRepository` is monkeypatched per test
-- this file is about the route's auth/response-shape behavior, not
`CustomerRepository` itself (covered in
`tests/unit/database/repositories/test_customer.py`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import backend.api.routes.customers as customers_route
from backend.database.enums import CustomerTier, UserRole
from backend.database.models.customer import Customer


class _NoOpSession:
    """A session double for the route's own `async with async_session_factory()`
    -- `CustomerRepository` is monkeypatched per test, so the session itself
    is never actually used."""

    async def __aenter__(self) -> _NoOpSession:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def _customers_route_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers_route, "async_session_factory", lambda: _NoOpSession())


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _customer(name: str = "Jane Doe") -> Customer:
    return Customer(
        id=uuid.uuid4(),
        name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        company="Acme",
        tier=CustomerTier.STANDARD,
        created_at=datetime.now(UTC),
    )


def test_list_customers_without_a_token_is_401(client: TestClient) -> None:
    response = client.get("/customers")
    assert response.status_code == 401


def test_list_customers_returns_seeded_customers(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    customers = [_customer("Jane Doe"), _customer("John Smith")]

    class _FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def list_all(self, *, limit: int = 100) -> list[Customer]:
            return customers

    monkeypatch.setattr(customers_route, "CustomerRepository", _FakeRepository)

    token = issue_token(UserRole.AGENT)
    response = client.get("/customers", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["name"] for item in body["items"]} == {"Jane Doe", "John Smith"}
    assert body["items"][0]["customer_id"] == str(customers[0].id)


def test_list_customers_empty_returns_empty_list(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def list_all(self, *, limit: int = 100) -> list[Customer]:
            return []

    monkeypatch.setattr(customers_route, "CustomerRepository", _FakeRepository)

    token = issue_token(UserRole.AGENT)
    response = client.get("/customers", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
