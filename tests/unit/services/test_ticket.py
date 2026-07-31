"""Unit tests for `backend.services.ticket.create_ticket`'s idempotency orchestration.

`_execute` (Postgres write + the LangGraph workflow) is monkeypatched --
this module is about the idempotency wiring, not ticket persistence or the
workflow itself (covered elsewhere). A shared `fakeredis.FakeAsyncRedis`
stands in for Redis via `get_redis_client`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import fakeredis
import pytest

import backend.services.ticket as ticket_service
from backend.database.enums import TicketPriority
from backend.schemas.ticket import TicketCreateRequest, TicketCreateResponse
from backend.services.idempotency import IdempotencyBackendUnavailable
from backend.services.ticket import TicketCreationInProgress, create_ticket


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeAsyncRedis:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(ticket_service, "get_redis_client", lambda: client)
    return client


@pytest.fixture
def payload() -> TicketCreateRequest:
    return TicketCreateRequest(
        customer_id=uuid.uuid4(),
        subject="Billing issue",
        description="I was billed twice",
        priority=TicketPriority.HIGH,
    )


def _fake_response(payload: TicketCreateRequest) -> TicketCreateResponse:
    return TicketCreateResponse(
        ticket_id=uuid.uuid4(),
        customer_id=payload.customer_id,
        category="billing",
        selected_agent="billing_agent",
        draft_response="Thanks for reaching out.",
        requires_human_review=False,
        matched_policy_rules=[],
        created_at=datetime.now(UTC),
    )


async def test_no_idempotency_key_always_executes(
    monkeypatch: pytest.MonkeyPatch, payload: TicketCreateRequest
) -> None:
    call_count = 0

    async def fake_execute(_payload: TicketCreateRequest) -> TicketCreateResponse:
        nonlocal call_count
        call_count += 1
        return _fake_response(_payload)

    monkeypatch.setattr(ticket_service, "_execute", fake_execute)

    await create_ticket(payload, None)
    await create_ticket(payload, None)

    assert call_count == 2


async def test_duplicate_key_executes_only_once_and_replays_response(
    monkeypatch: pytest.MonkeyPatch, payload: TicketCreateRequest
) -> None:
    call_count = 0

    async def fake_execute(_payload: TicketCreateRequest) -> TicketCreateResponse:
        nonlocal call_count
        call_count += 1
        return _fake_response(_payload)

    monkeypatch.setattr(ticket_service, "_execute", fake_execute)

    first = await create_ticket(payload, "my-key")
    second = await create_ticket(payload, "my-key")

    assert call_count == 1
    assert second.ticket_id == first.ticket_id
    assert first.idempotent_replay is False
    assert second.idempotent_replay is True


async def test_different_keys_both_execute(
    monkeypatch: pytest.MonkeyPatch, payload: TicketCreateRequest
) -> None:
    call_count = 0

    async def fake_execute(_payload: TicketCreateRequest) -> TicketCreateResponse:
        nonlocal call_count
        call_count += 1
        return _fake_response(_payload)

    monkeypatch.setattr(ticket_service, "_execute", fake_execute)

    first = await create_ticket(payload, "key-a")
    second = await create_ticket(payload, "key-b")

    assert call_count == 2
    assert first.ticket_id != second.ticket_id


async def test_concurrent_request_with_same_key_raises_in_progress(
    monkeypatch: pytest.MonkeyPatch,
    payload: TicketCreateRequest,
    _fake_redis: fakeredis.FakeAsyncRedis,
) -> None:
    """Simulates a second request arriving while the first hasn't completed:
    directly claim the key first, then call create_ticket with the same key."""
    from backend.config.settings import get_settings
    from backend.services.idempotency import IdempotencyStore

    settings = get_settings()
    store = IdempotencyStore(_fake_redis, ttl_seconds=settings.redis_idempotency_ttl_seconds)
    await store.claim_or_get_existing("in-flight-key")

    async def fake_execute(_payload: TicketCreateRequest) -> TicketCreateResponse:
        raise AssertionError("should not execute while another request holds the claim")

    monkeypatch.setattr(ticket_service, "_execute", fake_execute)

    with pytest.raises(TicketCreationInProgress):
        await create_ticket(payload, "in-flight-key")


async def test_execution_failure_releases_the_claim_for_a_retry(
    monkeypatch: pytest.MonkeyPatch, payload: TicketCreateRequest
) -> None:
    attempt = 0

    async def flaky_execute(_payload: TicketCreateRequest) -> TicketCreateResponse:
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise RuntimeError("workflow blew up")
        return _fake_response(_payload)

    monkeypatch.setattr(ticket_service, "_execute", flaky_execute)

    with pytest.raises(RuntimeError):
        await create_ticket(payload, "retry-key")

    # The failed attempt's claim must have been released -- a retry with the
    # same key should execute again, not be stuck as "in progress" forever.
    response = await create_ticket(payload, "retry-key")
    assert attempt == 2
    assert response.idempotent_replay is False


async def test_redis_unavailable_raises_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch, payload: TicketCreateRequest
) -> None:
    class _RaisingClient:
        async def set(self, *args: Any, **kwargs: Any) -> None:
            from redis.exceptions import RedisError

            raise RedisError("connection refused")

    monkeypatch.setattr(ticket_service, "get_redis_client", lambda: _RaisingClient())

    async def fake_execute(_payload: TicketCreateRequest) -> TicketCreateResponse:
        raise AssertionError("must fail closed before executing")

    monkeypatch.setattr(ticket_service, "_execute", fake_execute)

    with pytest.raises(IdempotencyBackendUnavailable):
        await create_ticket(payload, "some-key")
