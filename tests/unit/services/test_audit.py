"""Smoke test for the placeholder audit-logging service."""

import uuid

from backend.services.audit import log_audit_event


def test_log_audit_event_does_not_raise() -> None:
    log_audit_event(
        ticket_id=uuid.uuid4(),
        event_type="test_event",
        description="Test description.",
    )
