"""Unit tests for the audit-logging service.

`AuditLogRepository.create` is monkeypatched (no test database exists yet;
see `tests/unit/core/test_rate_limit.py`), so these exercise
`log_audit_event`'s own behavior: it persists via the repository, and a
persistence failure is swallowed (logged, never raised) rather than
crashing the caller.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from backend.database.repositories.audit_log import AuditLogRepository
from backend.services.audit import log_audit_event


async def test_log_audit_event_does_not_raise_when_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_create(self: AuditLogRepository, **kwargs: Any) -> None:
        raise RuntimeError("no database configured for this test")

    monkeypatch.setattr(AuditLogRepository, "create", failing_create)

    await log_audit_event(
        ticket_id=uuid.uuid4(),
        event_type="test_event",
        description="Test description.",
    )


async def test_log_audit_event_persists_via_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create(self: AuditLogRepository, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(AuditLogRepository, "create", fake_create)

    ticket_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await log_audit_event(
        ticket_id=ticket_id,
        event_type="supervisor_approved",
        description="Supervisor approved the AI draft response.",
        user_id=user_id,
        metadata={"comments": "looks good"},
    )

    assert captured["ticket_id"] == ticket_id
    assert captured["event_type"] == "supervisor_approved"
    assert captured["user_id"] == user_id
    assert captured["metadata"] == {"comments": "looks good"}


async def test_log_audit_event_defaults_metadata_to_empty_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_create(self: AuditLogRepository, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(AuditLogRepository, "create", fake_create)

    await log_audit_event(
        ticket_id=uuid.uuid4(), event_type="ai_draft_created", description="No metadata given."
    )

    assert captured["metadata"] == {}
    assert captured["user_id"] is None
