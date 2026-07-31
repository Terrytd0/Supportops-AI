"""Shared API rate limiting, backed by Redis (with an in-memory fallback).

`limiter` is the single `Limiter` instance every rate-limited route decorates
with `@limiter.limit(...)`; `configure_rate_limiting(app)` wires it into the
FastAPI app (state, 429 exception handler, enforcement middleware) once, from
`backend/main.py` at application startup -- the same pattern as
`configure_logging()`.

Per-route limits are declared as module-level constants next to the routes
they guard (e.g. `backend/auth/router.py`, `backend/api/supervisor.py`) so
they stay easy to find and change.

Distributed by design: counters live in Redis (`storage_uri`), shared across
every process/instance, not just the worker that handled a given request.
Short connect/socket timeouts (`storage_options`) plus
`in_memory_fallback_enabled=True` mean a Redis outage degrades to a
per-process in-memory limit (`_REDIS_OUTAGE_FALLBACK_LIMIT`) rather than
blocking every request on a slow timeout or taking rate limiting down
entirely -- verified empirically: the first request after an outage begins
pays one bounded timeout, every request after that is instant. Note this
fallback limit is a single blanket ceiling applied while Redis is down, not
a re-application of each route's own `@limiter.limit(...)` value -- see
`docs/architecture.md`'s Redis section for the full trade-off.

Rate-limit *keys* come from `_resolve_key`, which defers to a resolver
`backend.auth` registers at startup (`register_key_resolver`, called from
`backend/main.py`) rather than importing `backend.auth.jwt` directly here --
`backend/core/` is framework-level infra other layers depend on, not the
reverse (see CLAUDE.md's layering rules). Falls back to IP-based keying
until a resolver is registered (e.g. in a test importing this module
directly) or when no bearer token is present.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.config.settings import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# A Redis outage's blanket fallback ceiling -- deliberately closer to the
# strictest existing per-route limit (login's 5/minute) than the loosest,
# since during an outage this is the *only* limit protecting every route at
# once, not each route's own calibrated value. Tune via settings if needed.
_REDIS_OUTAGE_FALLBACK_LIMIT = "20/minute"

_key_resolver: Callable[[Request], str] | None = None


def register_key_resolver(resolver: Callable[[Request], str]) -> None:
    """Supply user-aware rate-limit key resolution from a higher layer.

    Called once from `backend/main.py` with
    `backend.auth.rate_limit_key.resolve_rate_limit_key`. Keeping this as a
    registration hook (rather than `core/` importing `backend.auth.jwt`
    directly) is what lets rate limiting key by authenticated user without
    inverting the dependency direction between `backend/core/` and
    `backend/auth/`.
    """
    global _key_resolver
    _key_resolver = resolver


def _resolve_key(request: Request) -> str:
    if _key_resolver is not None:
        return _key_resolver(request)
    return f"ip:{get_remote_address(request)}"


def _log_and_handle_rate_limit_exceeded(request: Request, exc: Exception) -> Response:
    """Log the throttled request, then return slowapi's standard 429 response.

    Typed as `Exception` (rather than `RateLimitExceeded`) to match
    `Starlette.add_exception_handler`'s expected signature; the assert holds
    because this handler is only ever registered for `RateLimitExceeded`.
    """
    assert isinstance(exc, RateLimitExceeded)
    logger.warning(
        "Rate limit exceeded for %s on %s %s",
        _resolve_key(request),
        request.method,
        request.url.path,
    )
    return _rate_limit_exceeded_handler(request, exc)


def _build_limiter() -> Limiter:
    settings = get_settings()
    # `storage_options` is typed as `Dict[str, str]` upstream, but these
    # keys are passed straight through to redis-py, which accepts (and
    # documents) float timeouts -- verified empirically against a real
    # (unreachable) Redis connection.
    storage_options: dict[str, Any] = {
        "socket_connect_timeout": settings.redis_connect_timeout_seconds,
        "socket_timeout": settings.redis_connect_timeout_seconds,
    }
    return Limiter(
        key_func=_resolve_key,
        storage_uri=settings.redis_url,
        storage_options=storage_options,
        in_memory_fallback_enabled=True,
        in_memory_fallback=[_REDIS_OUTAGE_FALLBACK_LIMIT],
    )


limiter = _build_limiter()


def configure_rate_limiting(app: FastAPI) -> None:
    """Attach `limiter` to `app` and install its 429 handler/middleware."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _log_and_handle_rate_limit_exceeded)
    app.add_middleware(SlowAPIMiddleware)
