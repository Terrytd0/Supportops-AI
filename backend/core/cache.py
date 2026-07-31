"""Generic Redis-backed cache for expensive, idempotent AI operations.

`RedisCache` is the one place cache get/set/hash/TTL/graceful-degradation
logic lives, shared by `backend.graph.classifier` (ticket classification)
and `backend.tools.knowledge_base` (knowledge-base retrieval) rather than
each hand-rolling its own Redis calls -- see backend/core/README.md.

Cache misses on error: any `redis.RedisError` (Redis down, timed out, ...)
is treated as a miss on read and a no-op on write, logged as a warning.
Caching is a pure performance optimization here -- unlike idempotency,
there is no correctness reason to ever fail a request because the cache is
unavailable.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.core.logging import get_logger

logger = get_logger(__name__)

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Collapse whitespace and lowercase, so trivially-different inputs
    ("Refund please", "refund   please") share one cache entry."""
    return _WHITESPACE_PATTERN.sub(" ", text).strip().lower()


def build_cache_key(key_prefix: str, *parts: str) -> str:
    """Hash `parts` (already-normalized strings) into one cache key under `key_prefix`.

    A module-level function, not just `RedisCache.build_key`, so a cache key
    can be computed without needing a `RedisCache` instance -- and so
    without needing `backend.core.redis_client.get_redis_client()`, which
    must only be called from inside a running event loop (see that
    module's docstring). Callers like `backend.graph.classifier` compute
    their cache key up front, in plain sync code, then defer the client
    resolution to a small `async def` passed to `run_sync`.
    """
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()
    return f"{key_prefix}:{digest}"


class RedisCache:
    """A namespaced, TTL'd, JSON-valued cache over a single Redis client."""

    def __init__(self, client: Redis, *, key_prefix: str, ttl_seconds: int) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    def build_key(self, *parts: str) -> str:
        """Hash `parts` (already-normalized strings) into one cache key."""
        return build_cache_key(self._key_prefix, *parts)

    async def get(self, key: str) -> Any | None:
        """Return the cached value for `key`, or `None` on a miss or any failure."""
        try:
            raw = await self._client.get(key)
        except RedisError as exc:
            logger.warning("Cache read failed", extra={"key": key, "error": str(exc)})
            return None

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Cached value was not valid JSON", extra={"key": key})
            return None

    async def set(self, key: str, value: Any) -> None:
        """Cache `value` under `key` with this cache's configured TTL.

        `default=str` handles the odd non-JSON-native type (UUID, ...)
        transparently; never raises.
        """
        try:
            await self._client.set(key, json.dumps(value, default=str), ex=self._ttl_seconds)
        except RedisError as exc:
            logger.warning("Cache write failed", extra={"key": key, "error": str(exc)})
