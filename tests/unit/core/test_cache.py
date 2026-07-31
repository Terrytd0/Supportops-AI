"""Unit tests for the generic Redis-backed AI-operation cache.

Uses `fakeredis.FakeAsyncRedis` (an in-memory `redis.asyncio`-compatible
server) for real get/set/TTL behavior, plus a raising double to verify
failures degrade to a miss/no-op rather than propagating.
"""

from __future__ import annotations

import fakeredis
import pytest
from redis.exceptions import RedisError

from backend.core.cache import RedisCache, normalize_text


@pytest.fixture
def fake_client() -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(decode_responses=True)


def test_normalize_text_collapses_whitespace_and_case() -> None:
    assert normalize_text("  Invoice   Charged\tTwice  ") == "invoice charged twice"


def test_build_key_is_deterministic_for_the_same_parts(
    fake_client: fakeredis.FakeAsyncRedis,
) -> None:
    cache = RedisCache(fake_client, key_prefix="test", ttl_seconds=60)
    assert cache.build_key("a", "b") == cache.build_key("a", "b")
    assert cache.build_key("a", "b") != cache.build_key("a", "c")


async def test_get_is_a_miss_when_never_set(fake_client: fakeredis.FakeAsyncRedis) -> None:
    cache = RedisCache(fake_client, key_prefix="test", ttl_seconds=60)

    assert await cache.get(cache.build_key("nope")) is None


async def test_set_then_get_is_a_hit(fake_client: fakeredis.FakeAsyncRedis) -> None:
    cache = RedisCache(fake_client, key_prefix="test", ttl_seconds=60)
    key = cache.build_key("billing", "invoice charged twice")

    await cache.set(key, {"category": "billing"})

    assert await cache.get(key) == {"category": "billing"}


async def test_set_applies_the_configured_ttl(fake_client: fakeredis.FakeAsyncRedis) -> None:
    cache = RedisCache(fake_client, key_prefix="test", ttl_seconds=123)
    key = cache.build_key("x")

    await cache.set(key, "value")

    assert await fake_client.ttl(key) == 123


async def test_get_returns_none_and_logs_on_malformed_cached_value(
    fake_client: fakeredis.FakeAsyncRedis,
) -> None:
    cache = RedisCache(fake_client, key_prefix="test", ttl_seconds=60)
    key = cache.build_key("x")
    await fake_client.set(key, "not valid json {{{")

    assert await cache.get(key) is None


async def test_get_degrades_to_none_on_redis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RaisingClient:
        async def get(self, _key: str) -> str:
            raise RedisError("connection refused")

    cache = RedisCache(_RaisingClient(), key_prefix="test", ttl_seconds=60)  # type: ignore[arg-type]

    assert await cache.get("some-key") is None


async def test_set_swallows_redis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RaisingClient:
        async def set(self, *args: object, **kwargs: object) -> None:
            raise RedisError("connection refused")

    cache = RedisCache(_RaisingClient(), key_prefix="test", ttl_seconds=60)  # type: ignore[arg-type]

    await cache.set("some-key", "value")  # must not raise
