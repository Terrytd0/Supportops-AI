"""FastAPI application entry point.

TODO: register additional routers as they are implemented (tickets,
conversations, agent runs), mount middleware (backend/api/middleware), and
add startup/shutdown hooks for database and Redis connection lifecycles.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from backend.api.routes.health import router as health_router
from backend.api.supervisor import router as supervisor_router
from backend.auth.router import router as auth_router
from backend.config.settings import get_settings
from backend.core.logging import configure_logging, get_logger
from backend.core.rate_limit import configure_rate_limiting

# Configured once, here, at application startup -- every other module just
# calls get_logger(__name__) and shares this handler/formatter.
configure_logging()
logger = get_logger(__name__)

settings = get_settings()

logger.info("Application startup: %s (environment=%s)", settings.app_name, settings.environment)

app = FastAPI(
    title=settings.app_name,
    description="Enterprise-grade multi-agent customer support platform.",
    version="0.1.0",
    debug=settings.debug,
)

configure_rate_limiting(app)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(supervisor_router)


@app.middleware("http")
async def log_unhandled_exceptions(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log unexpected exceptions before they hit Starlette's default 500 handler.

    Deliberately re-raises rather than returning a response: `HTTPException`s
    (401/403/404/422, ...) are already resolved to normal responses further
    down the middleware stack and never reach this `except`, so only
    genuinely unhandled errors are logged here, and the resulting response
    is unchanged from FastAPI's default behavior.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.error(
            "Unhandled exception on %s %s", request.method, request.url.path, exc_info=True
        )
        raise


@app.get("/")
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} is running."}
