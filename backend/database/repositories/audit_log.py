"""Repository for `AuditLog` writes.

Owns the only write `backend.services.audit.log_audit_event` needs: append
one immutable row per business/system action. Read-side queries (e.g. "list
audit history for a ticket") aren't needed by any caller yet -- see
`backend/database/README.md`'s TODOs.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.audit_log import AuditLog


class AuditLogRepository:
    """Write-only (so far) repository for the `audit_logs` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        ticket_id: uuid.UUID,
        event_type: str,
        description: str,
        user_id: uuid.UUID | None,
        metadata: dict[str, Any],
    ) -> AuditLog:
        record = AuditLog(
            ticket_id=ticket_id,
            user_id=user_id,
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )
        self._session.add(record)
        await self._session.flush()
        return record
