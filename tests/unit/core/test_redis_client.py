"""Unit tests for `get_redis_client`'s per-event-loop scoping.

`redis.asyncio.Redis`'s connections are bound to whichever event loop first
uses them, so a client must never be shared across more than one loop --
see `backend/core/redis_client.py`'s module docstring. These tests exercise
the real `get_redis_client()` (no monkeypatching): each check runs entirely
in-process, without needing a reachable Redis server, since `Redis.from_url`
itself never opens a connection -- only an actual command would, and none
of these tests issue one.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.core.redis_client import get_redis_client


async def _get_client():
    return get_redis_client()


def test_get_redis_client_requires_a_running_event_loop() -> None:
    with pytest.raises(RuntimeError):
        get_redis_client()


def test_get_redis_client_returns_the_same_instance_within_one_loop() -> None:
    async def _twice():
        first = get_redis_client()
        second = get_redis_client()
        return first, second

    first, second = asyncio.run(_twice())

    assert first is second


def test_get_redis_client_returns_different_instances_across_loops() -> None:
    """The core guarantee: two different event loops (e.g. FastAPI's own
    loop and run_sync's background loop) must never end up sharing a
    client, or one loop's closed connections get reused by the other."""
    first = asyncio.run(_get_client())
    second = asyncio.run(_get_client())

    assert first is not second
