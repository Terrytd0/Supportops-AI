"""Unit tests for `IdempotencyStore`.

Uses `fakeredis.FakeAsyncRedis` for real atomic-claim/TTL behavior, plus a
raising double to verify Redis failures raise `IdempotencyBackendUnavailable`
(fail *closed* -- the opposite of `RedisCache`/`WorkflowCheckpointStore` --
see the module docstring on why duplicate-prevention can't degrade silently).
"""

from __future__ import annotations

import fakeredis
import pytest
from redis.exceptions import RedisError

from backend.services.idempotency import IdempotencyBackendUnavailable, IdempotencyStore


@pytest.fixture
def fake_client() -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(decode_responses=True)


async def test_first_claim_returns_none(fake_client: fakeredis.FakeAsyncRedis) -> None:
    store = IdempotencyStore(fake_client, ttl_seconds=60)

    assert await store.claim_or_get_existing("key-1") is None


async def test_second_claim_before_completion_returns_in_progress(
    fake_client: fakeredis.FakeAsyncRedis,
) -> None:
    store = IdempotencyStore(fake_client, ttl_seconds=60)

    await store.claim_or_get_existing("key-1")
    result = await store.claim_or_get_existing("key-1")

    assert result == {"status": "in_progress"}


async def test_claim_after_completion_returns_the_stored_response(
    fake_client: fakeredis.FakeAsyncRedis,
) -> None:
    store = IdempotencyStore(fake_client, ttl_seconds=60)

    await store.claim_or_get_existing("key-1")
    await store.complete("key-1", {"ticket_id": "abc-123", "status": "created"})

    result = await store.claim_or_get_existing("key-1")

    assert result == {"ticket_id": "abc-123", "status": "created"}


async def test_release_allows_a_fresh_claim(fake_client: fakeredis.FakeAsyncRedis) -> None:
    store = IdempotencyStore(fake_client, ttl_seconds=60)

    await store.claim_or_get_existing("key-1")
    await store.release("key-1")

    assert await store.claim_or_get_existing("key-1") is None


async def test_claim_applies_the_configured_ttl(fake_client: fakeredis.FakeAsyncRedis) -> None:
    store = IdempotencyStore(fake_client, ttl_seconds=99)

    await store.claim_or_get_existing("key-1")

    assert await fake_client.ttl(store._key("key-1")) == 99


async def test_different_keys_are_independent(fake_client: fakeredis.FakeAsyncRedis) -> None:
    store = IdempotencyStore(fake_client, ttl_seconds=60)

    await store.claim_or_get_existing("key-1")

    assert await store.claim_or_get_existing("key-2") is None


async def test_claim_raises_backend_unavailable_on_redis_error() -> None:
    class _RaisingClient:
        async def set(self, *args: object, **kwargs: object) -> None:
            raise RedisError("connection refused")

    store = IdempotencyStore(_RaisingClient(), ttl_seconds=60)  # type: ignore[arg-type]

    with pytest.raises(IdempotencyBackendUnavailable):
        await store.claim_or_get_existing("key-1")


async def test_complete_raises_backend_unavailable_on_redis_error() -> None:
    class _RaisingClient:
        async def set(self, *args: object, **kwargs: object) -> None:
            raise RedisError("connection refused")

    store = IdempotencyStore(_RaisingClient(), ttl_seconds=60)  # type: ignore[arg-type]

    with pytest.raises(IdempotencyBackendUnavailable):
        await store.complete("key-1", {"ok": True})


async def test_release_swallows_redis_error() -> None:
    class _RaisingClient:
        async def delete(self, *args: object) -> None:
            raise RedisError("connection refused")

    store = IdempotencyStore(_RaisingClient(), ttl_seconds=60)  # type: ignore[arg-type]

    await store.release("key-1")  # must not raise
