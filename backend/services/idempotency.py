"""Redis-backed idempotency for client-initiated write operations.

`IdempotencyStore` guarantees at-most-once execution per `Idempotency-Key`:
the first request to claim a key runs the real operation and stores its
response; every later request with the same key gets back the *original*
response instead of re-running anything (`backend/api/routes/tickets.py`).

Fails CLOSED, not open -- the opposite of `backend.core.cache`. A cache miss
on a Redis failure just means "compute it again," always safe. Here,
failing open (proceeding without being able to check for a duplicate) could
let a genuine duplicate through, and "duplicate ticket creation must never
occur" is a correctness requirement, not a performance nicety. So a
`redis.RedisError` here is raised as `IdempotencyBackendUnavailable` rather
than swallowed, and the route turns that into a clear 503 telling the
client to retry -- an honest failure instead of a silent risk.

Claiming is atomic (`SET key ... NX EX ttl`): the first caller to succeed
owns the key and must call `complete()` (on success) or `release()` (on
failure, so a failed attempt doesn't block retries for the rest of the
TTL); every other concurrent caller sees the in-progress sentinel and
should tell its client to retry shortly.
"""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.core.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "idempotency"
_IN_PROGRESS_SENTINEL = {"status": "in_progress"}


class IdempotencyBackendUnavailable(Exception):
    """Raised when Redis can't be reached to check/claim an idempotency key.

    Deliberately not swallowed -- see module docstring.
    """


class IdempotencyStore:
    def __init__(self, client: Redis, *, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    def _key(self, idempotency_key: str) -> str:
        return f"{_KEY_PREFIX}:{idempotency_key}"

    async def claim_or_get_existing(self, idempotency_key: str) -> dict[str, Any] | None:
        """Atomically claim `idempotency_key`, or return what's already there.

        Returns `None` if this call claimed the key -- the caller must
        proceed to execute the operation and call `complete()`/`release()`.
        Otherwise returns the existing value: a previously completed
        response, or `{"status": "in_progress"}` if another request is
        still executing.
        """
        try:
            claimed = await self._client.set(
                self._key(idempotency_key),
                json.dumps(_IN_PROGRESS_SENTINEL),
                nx=True,
                ex=self._ttl_seconds,
            )
        except RedisError as exc:
            raise IdempotencyBackendUnavailable(str(exc)) from exc

        if claimed:
            return None

        try:
            raw = await self._client.get(self._key(idempotency_key))
        except RedisError as exc:
            raise IdempotencyBackendUnavailable(str(exc)) from exc

        if raw is None:
            # Vanishingly rare: the key expired between our failed claim and
            # this read. We did not claim it, so we do not proceed as if we
            # had; the caller should simply retry.
            return dict(_IN_PROGRESS_SENTINEL)

        try:
            result: dict[str, Any] = json.loads(raw)
            return result
        except (TypeError, ValueError):
            logger.warning(
                "Idempotency record was malformed", extra={"idempotency_key": idempotency_key}
            )
            return dict(_IN_PROGRESS_SENTINEL)

    async def complete(self, idempotency_key: str, response: dict[str, Any]) -> None:
        """Overwrite `idempotency_key`'s in-progress claim with the real response."""
        try:
            await self._client.set(
                self._key(idempotency_key),
                json.dumps(response, default=str),
                ex=self._ttl_seconds,
            )
        except RedisError as exc:
            raise IdempotencyBackendUnavailable(str(exc)) from exc

    async def release(self, idempotency_key: str) -> None:
        """Delete `idempotency_key`'s claim after a failed attempt, so a
        retry with the same key isn't blocked for the rest of the TTL."""
        try:
            await self._client.delete(self._key(idempotency_key))
        except RedisError as exc:
            logger.warning(
                "Failed to release idempotency key after a failed attempt",
                extra={"idempotency_key": idempotency_key, "error": str(exc)},
            )
