"""Placeholder audit-logging service.

Marks the single place downstream code (currently `backend/api/supervisor.py`)
calls to record a business/system action, without yet writing anywhere
durable. Centralizing the call site here — rather than logging ad hoc from
routes/nodes — means the eventual repository-backed implementation is a
one-file change.

No Postgres access. No repository implementation.

TODO(Repository): replace the body of `log_audit_event` with a write via an
`AuditLogRepository` (see `backend/database/repositories/`) against
`backend.database.models.audit_log.AuditLog`, inside the same transaction as
the action being recorded.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

_logger = logging.getLogger("supportops.audit")


def log_audit_event(
    *,
    ticket_id: uuid.UUID,
    event_type: str,
    description: str,
    user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a single audit event for `ticket_id`.

    Placeholder: emits a structured log line in place of an `audit_logs`
    row. Field names mirror `backend.database.models.audit_log.AuditLog`
    (`ticket_id`, `user_id`, `event_type`, `description`, `event_metadata`)
    so swapping in the real repository call is a drop-in replacement.

    Args:
        ticket_id: The ticket the event concerns.
        event_type: Short machine-readable event name (e.g. "supervisor_approved").
        description: Human-readable description of what happened.
        user_id: The acting user, if any (None for system-generated events).
        metadata: Additional structured context for the event.
    """
    _logger.info(
        "audit_event",
        extra={
            "ticket_id": str(ticket_id),
            "user_id": str(user_id) if user_id is not None else None,
            "event_type": event_type,
            "description": description,
            "metadata": metadata or {},
        },
    )
