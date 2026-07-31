"""Unit tests for `backend.services.ticket._execute`'s customer validation.

`_execute` is the one place that inserts a `Ticket` row, so it's also the
one place a nonexistent `customer_id` would otherwise surface as a raw
PostgreSQL foreign-key-violation 500 -- see `CustomerNotFound`. Idempotency
wiring around `_execute` is covered in `test_ticket.py`; the LangGraph
workflow it invokes is covered elsewhere (`tests/unit/graph/`).

No test database exists (see `tests/unit/core/test_rate_limit.py`), so
`async_session_factory`, `CustomerRepository`, and `TicketRepository` are all
faked/monkeypatched.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

import backend.services.ticket as ticket_service
from backend.database.enums import CustomerTier, TicketPriority
from backend.database.models.customer import Customer
from backend.database.models.ticket import Ticket
from backend.schemas.ticket import TicketCreateRequest
from backend.services.ticket import CustomerNotFound


class _NoOpSessionCM:
    def __init__(self, session: Any) -> None:
        self._session = session

    async def __aenter__(self) -> Any:
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeSession:
    """`commit`/`rollback` are no-ops -- these tests are about `_execute`'s
    control flow, not transaction mechanics."""

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@pytest.fixture
def payload() -> TicketCreateRequest:
    return TicketCreateRequest(
        customer_id=uuid.uuid4(),
        subject="Billing issue",
        description="I was billed twice",
        priority=TicketPriority.HIGH,
    )


@pytest.fixture(autouse=True)
def _session_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ticket_service, "async_session_factory", lambda: _NoOpSessionCM(_FakeSession())
    )


@pytest.fixture(autouse=True)
def _no_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails loudly if the workflow ever runs when a customer lookup should
    have short-circuited `_execute` first."""

    class _Graph:
        def invoke(self, _state: Any) -> Any:
            raise AssertionError("workflow must not run when the customer is invalid")

    monkeypatch.setattr(ticket_service, "get_graph", lambda: _Graph())


async def test_unknown_customer_raises_customer_not_found(
    monkeypatch: pytest.MonkeyPatch, payload: TicketCreateRequest
) -> None:
    class _FakeCustomerRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _customer_id: uuid.UUID) -> Customer | None:
            return None

    monkeypatch.setattr(ticket_service, "CustomerRepository", _FakeCustomerRepository)

    with pytest.raises(CustomerNotFound) as exc_info:
        await ticket_service._execute(payload)

    assert exc_info.value.customer_id == payload.customer_id


async def test_integrity_error_on_insert_is_translated_to_customer_not_found(
    monkeypatch: pytest.MonkeyPatch, payload: TicketCreateRequest
) -> None:
    """Defense in depth: even if the upfront check passes (e.g. a race with a
    customer deleted concurrently), a foreign-key violation on insert must
    still surface as `CustomerNotFound`, not an unhandled `IntegrityError`."""

    customer = Customer(
        id=payload.customer_id,
        name="Jane Doe",
        email="jane.doe@example.com",
        tier=CustomerTier.STANDARD,
    )

    class _FakeCustomerRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _customer_id: uuid.UUID) -> Customer | None:
            return customer

    class _FakeTicketRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def create(self, **_kwargs: Any) -> Ticket:
            raise IntegrityError("insert", {}, Exception("fk violation"))

    monkeypatch.setattr(ticket_service, "CustomerRepository", _FakeCustomerRepository)
    monkeypatch.setattr(ticket_service, "TicketRepository", _FakeTicketRepository)

    with pytest.raises(CustomerNotFound):
        await ticket_service._execute(payload)
