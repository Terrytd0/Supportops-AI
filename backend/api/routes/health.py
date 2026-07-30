"""Liveness/readiness endpoint.

TODO: extend readiness check to verify database and Redis connectivity once
those clients are wired up in backend/database and backend/services.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "ok"
    }