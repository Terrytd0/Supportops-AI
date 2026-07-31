"""Unit tests for `CustomerRepository`.

Uses a fake `AsyncSession` double (rather than a real database -- no test-DB
fixture exists yet, see `tests/unit/core/test_rate_limit.py`), same trick as
`tests/unit/database/repositories/test_knowledge_article.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.enums import CustomerTier
from backend.database.models.customer import Customer
from backend.database.repositories.customer import CustomerRepository


class _FakeScalars:
    def __init__(self, customers: list[Customer]) -> None:
        self._customers = customers

    def all(self) -> list[Customer]:
        return self._customers


class _FakeResult:
    def __init__(self, customers: list[Customer]) -> None:
        self._customers = customers

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._customers)


class _FakeSession:
    """Stands in for `AsyncSession`: `get()` looks up by id in an in-memory
    dict, `execute()` returns canned customers regardless of the statement."""

    def __init__(self, customers: list[Customer]) -> None:
        self._by_id = {customer.id: customer for customer in customers}
        self._customers = customers

    async def get(self, _model: type, id_: uuid.UUID) -> Customer | None:
        return self._by_id.get(id_)

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._customers)


def _customer(name: str = "Jane Doe", created_at: datetime | None = None) -> Customer:
    return Customer(
        id=uuid.uuid4(),
        name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        company="Acme",
        tier=CustomerTier.STANDARD,
        created_at=created_at or datetime.now(UTC),
    )


def _repository(*customers: Customer) -> CustomerRepository:
    return CustomerRepository(cast(AsyncSession, _FakeSession(list(customers))))


async def test_get_by_id_returns_matching_customer() -> None:
    customer = _customer()
    repository = _repository(customer)

    result = await repository.get_by_id(customer.id)

    assert result is customer


async def test_get_by_id_returns_none_for_unknown_id() -> None:
    repository = _repository(_customer())

    result = await repository.get_by_id(uuid.uuid4())

    assert result is None


async def test_list_all_returns_every_customer() -> None:
    customers = [_customer(f"Customer {i}") for i in range(3)]
    repository = _repository(*customers)

    result = await repository.list_all()

    assert result == customers
