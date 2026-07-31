"""Reusable Redis client -- the single place `redis.asyncio.Redis` is constructed.

Every Redis-backed feature (distributed rate limiting, idempotency,
workflow checkpoints, AI/knowledge caches) goes through `get_redis_client()`
rather than constructing its own connection, so pool wiring and timeouts
live in one place instead of being scattered across the codebase.

Redis is ephemeral infrastructure, never the system of record (see
docs/architecture.md): this client is configured with short connect/socket
timeouts so a Redis outage fails fast, but it does not itself swallow
`redis.RedisError` -- each caller decides how to degrade (a cache treats a
failure as a miss; idempotency-key checking fails closed instead), so that
decision stays with the feature that understands its own correctness
requirements. See `backend/core/README.md`.

Loop-scoped, not one process-wide singleton: `redis.asyncio.Redis`'s
connections (and the asyncio primitives they use internally) are bound to
whichever event loop first uses them, and must never be reused from a
different one -- see `backend/core/asyncio_utils.py`'s module docstring for
the failure this causes ("Future attached to a different loop") and why
this codebase legitimately runs two long-lived loops: FastAPI's own
request-handling loop (used directly by e.g.
`backend.services.idempotency.IdempotencyStore`, `backend.core.rate_limit`)
and `run_sync`'s dedicated background loop (used by everything invoked from
LangGraph's worker thread). `get_redis_client()` therefore hands out one
client per *calling* loop, cached in a `WeakKeyDictionary` keyed by the loop
object itself so an entry is dropped automatically if its loop ever is
(never happens for either of the two loops above in practice, but matters
for e.g. tests that spin up many short-lived loops).

Must be called from inside a running event loop -- deferred, lazily, to the
moment right before an actual Redis operation runs, never eagerly in plain
synchronous code (see the call sites in `backend/graph/classifier.py`,
`backend/graph/nodes.py`, and `backend/tools/knowledge_base.py`, all of
which resolve their client from inside a coroutine passed to `run_sync`).
"""

from __future__ import annotations

import asyncio
import weakref

import redis.asyncio as redis

from backend.config.settings import get_settings

_clients_by_loop: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, redis.Redis] = (
    weakref.WeakKeyDictionary()
)


def get_redis_client() -> redis.Redis:
    """Return the calling event loop's Redis client, building it on first use.

    Must be called from inside a running event loop (raises `RuntimeError`
    via `asyncio.get_running_loop()` otherwise) -- see the module docstring
    on why a client must never be shared across more than one loop.
    """
    loop = asyncio.get_running_loop()
    client = _clients_by_loop.get(loop)
    if client is None:
        settings = get_settings()
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.redis_connect_timeout_seconds,
            socket_timeout=settings.redis_connect_timeout_seconds,
            decode_responses=True,
        )
        _clients_by_loop[loop] = client
    return client
