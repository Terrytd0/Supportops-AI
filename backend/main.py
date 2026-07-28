"""FastAPI application entry point.

TODO: register additional routers as they are implemented (tickets,
conversations, agent runs), mount middleware (backend/api/middleware), and
add startup/shutdown hooks for database and Redis connection lifecycles.
"""

from fastapi import FastAPI

from backend.api.routes.health import router as health_router
from backend.auth.router import router as auth_router
from backend.config.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Enterprise-grade multi-agent customer support platform.",
    version="0.1.0",
    debug=settings.debug,
)

app.include_router(health_router)
app.include_router(auth_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} is running."}
