"""Shared API rate limiting, backed by slowapi's in-process memory store.

`limiter` is the single `Limiter` instance every rate-limited route decorates
with `@limiter.limit(...)`; `configure_rate_limiting(app)` wires it into the
FastAPI app (state, 429 exception handler, enforcement middleware) once, from
`backend/main.py` at application startup -- the same pattern as
`configure_logging()`.

Per-route limits are declared as module-level constants next to the routes
they guard (e.g. `backend/auth/router.py`, `backend/api/supervisor.py`) so
they stay easy to find and change.

TODO: swap the default in-memory storage for a Redis-backed storage URI once
Redis is introduced, so limits are shared across processes/instances instead
of tracked per-worker.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Keyed by client IP; no Redis storage configured yet, so counters live only
# in this process's memory (see TODO above).
limiter = Limiter(key_func=get_remote_address)


def _log_and_handle_rate_limit_exceeded(request: Request, exc: Exception) -> Response:
    """Log the throttled request, then return slowapi's standard 429 response.

    Typed as `Exception` (rather than `RateLimitExceeded`) to match
    `Starlette.add_exception_handler`'s expected signature; the assert holds
    because this handler is only ever registered for `RateLimitExceeded`.
    """
    assert isinstance(exc, RateLimitExceeded)
    logger.warning(
        "Rate limit exceeded for %s on %s %s",
        get_remote_address(request),
        request.method,
        request.url.path,
    )
    return _rate_limit_exceeded_handler(request, exc)


def configure_rate_limiting(app: FastAPI) -> None:
    """Attach `limiter` to `app` and install its 429 handler/middleware."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _log_and_handle_rate_limit_exceeded)
    app.add_middleware(SlowAPIMiddleware)
