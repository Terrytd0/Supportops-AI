"""Audit-logging service: the one call site every action-recording caller uses.

Centralizing the call site here -- rather than logging/writing ad hoc from
routes/nodes -- means callers (`backend/api/supervisor.py`,
`backend.graph.nodes.persist_results_node`) never touch
`AuditLogRepository` directly.

Persistence is best-effort: a failed write (no reachable database, a bad
`ticket_id`, ...) is logged as a warning, never raised, so a missing audit
row never crashes the caller -- the structured log line below is always
emitted regardless, so the event is never silently lost from observability
even when Postgres is unavailable.
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.core.logging import get_logger
from backend.database.repositories.audit_log import AuditLogRepository
from backend.database.session import async_session_factory

logger = get_logger(__name__)


async def log_audit_event(
    *,
    ticket_id: uuid.UUID,
    event_type: str,
    description: str,
    user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a single audit event for `ticket_id`.

    Args:
        ticket_id: The ticket the event concerns.
        event_type: Short machine-readable event name (e.g. "supervisor_approved").
        description: Human-readable description of what happened.
        user_id: The acting user, if any (None for system-generated events,
            e.g. "ai_draft_created").
        metadata: Additional structured context for the event.
    """
    logger.info(
        "Audit log created: ticket=%s event_type=%s user=%s",
        ticket_id,
        event_type,
        user_id if user_id is not None else "system",
        extra={
            "ticket_id": str(ticket_id),
            "user_id": str(user_id) if user_id is not None else None,
            "event_type": event_type,
            "description": description,
            "metadata": metadata or {},
        },
    )

    try:
        async with async_session_factory() as session:
            repository = AuditLogRepository(session)
            await repository.create(
                ticket_id=ticket_id,
                event_type=event_type,
                description=description,
                user_id=user_id,
                metadata=metadata or {},
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "Failed to persist audit log row",
            extra={"ticket_id": str(ticket_id), "event_type": event_type, "error": str(exc)},
        )
