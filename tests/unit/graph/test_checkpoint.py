"""Unit tests for `WorkflowCheckpointStore`.

Uses `fakeredis.FakeAsyncRedis` for real save/recover round trips, plus a
raising double to verify Redis failures degrade to "no checkpoint" rather
than propagating (checkpoints are diagnostic/best-effort only -- see the
module docstring).
"""

from __future__ import annotations

import uuid

import fakeredis
import pytest
from redis.exceptions import RedisError

from backend.graph.checkpoint import WorkflowCheckpointStore


@pytest.fixture
def fake_client() -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(decode_responses=True)


async def test_get_latest_is_none_when_nothing_saved(fake_client: fakeredis.FakeAsyncRedis) -> None:
    store = WorkflowCheckpointStore(fake_client, ttl_seconds=60)

    assert await store.get_latest(uuid.uuid4()) is None


async def test_save_then_get_latest_round_trips(fake_client: fakeredis.FakeAsyncRedis) -> None:
    store = WorkflowCheckpointStore(fake_client, ttl_seconds=60)
    ticket_id = uuid.uuid4()

    await store.save(ticket_id=ticket_id, stage="classification", snapshot={"category": "billing"})
    checkpoint = await store.get_latest(ticket_id)

    assert checkpoint is not None
    assert checkpoint.ticket_id == ticket_id
    assert checkpoint.stage == "classification"
    assert checkpoint.snapshot == {"category": "billing"}


async def test_save_overwrites_the_previous_checkpoint(
    fake_client: fakeredis.FakeAsyncRedis,
) -> None:
    """One evolving checkpoint per ticket, not a full history."""
    store = WorkflowCheckpointStore(fake_client, ttl_seconds=60)
    ticket_id = uuid.uuid4()

    await store.save(ticket_id=ticket_id, stage="classification", snapshot={"category": "billing"})
    await store.save(
        ticket_id=ticket_id, stage="agent_selection", snapshot={"selected_agent": "billing_agent"}
    )

    checkpoint = await store.get_latest(ticket_id)
    assert checkpoint is not None
    assert checkpoint.stage == "agent_selection"
    assert checkpoint.snapshot == {"selected_agent": "billing_agent"}


async def test_save_applies_the_configured_ttl(fake_client: fakeredis.FakeAsyncRedis) -> None:
    store = WorkflowCheckpointStore(fake_client, ttl_seconds=42)
    ticket_id = uuid.uuid4()

    await store.save(ticket_id=ticket_id, stage="classification", snapshot={})

    key = store._key(ticket_id)
    assert await fake_client.ttl(key) == 42


async def test_save_serializes_uuids_and_enums(fake_client: fakeredis.FakeAsyncRedis) -> None:
    """Confirms `json.dumps(..., default=str)` handles WorkflowState's
    non-JSON-native field types (UUIDs, str-enums) transparently."""
    from backend.graph.state import SupportAgentType, TicketCategory

    store = WorkflowCheckpointStore(fake_client, ttl_seconds=60)
    ticket_id = uuid.uuid4()
    other_id = uuid.uuid4()

    await store.save(
        ticket_id=ticket_id,
        stage="agent_selection",
        snapshot={
            "selected_agent": SupportAgentType.BILLING_AGENT,
            "category": TicketCategory.BILLING,
            "related_id": other_id,
        },
    )

    checkpoint = await store.get_latest(ticket_id)
    assert checkpoint is not None
    assert checkpoint.snapshot["selected_agent"] == "billing_agent"
    assert checkpoint.snapshot["category"] == "billing"
    assert checkpoint.snapshot["related_id"] == str(other_id)


async def test_get_latest_returns_none_on_malformed_payload(
    fake_client: fakeredis.FakeAsyncRedis,
) -> None:
    store = WorkflowCheckpointStore(fake_client, ttl_seconds=60)
    ticket_id = uuid.uuid4()
    await fake_client.set(store._key(ticket_id), "not valid json {{{")

    assert await store.get_latest(ticket_id) is None


async def test_get_latest_degrades_to_none_on_redis_error() -> None:
    class _RaisingClient:
        async def get(self, _key: str) -> str:
            raise RedisError("connection refused")

    store = WorkflowCheckpointStore(_RaisingClient(), ttl_seconds=60)  # type: ignore[arg-type]

    assert await store.get_latest(uuid.uuid4()) is None


async def test_save_swallows_redis_error() -> None:
    class _RaisingClient:
        async def set(self, *args: object, **kwargs: object) -> None:
            raise RedisError("connection refused")

    store = WorkflowCheckpointStore(_RaisingClient(), ttl_seconds=60)  # type: ignore[arg-type]

    await store.save(ticket_id=uuid.uuid4(), stage="classification", snapshot={})  # must not raise
