"""Tests for the supervisor approval-queue endpoints.

`ApprovalRequestRepository` methods are monkeypatched per test (no real
database -- see `tests/unit/api/conftest.py`); auth is exercised for real
(real JWTs via `issue_token`, decoded by the real `require_role`/
`get_current_user` dependency chain -- only the DB user lookup is faked).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.database.enums import UserRole
from backend.database.repositories.approval_request import ApprovalRequestRepository
from tests.unit.api.conftest import build_approval_request

_KNOWN_TICKET_ID = "00000000-0000-0000-0000-000000000001"
_UNKNOWN_TICKET_ID = "00000000-0000-0000-0000-000000009999"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Authentication / authorization ---


def test_list_queue_without_a_token_is_401(client: TestClient) -> None:
    response = client.get("/supervisor/queue")
    assert response.status_code == 401


def test_list_queue_forbidden_for_agent_role(client: TestClient, issue_token) -> None:
    token = issue_token(UserRole.AGENT)
    response = client.get("/supervisor/queue", headers=_auth_headers(token))
    assert response.status_code == 403


def test_approve_forbidden_for_agent_role(client: TestClient, issue_token) -> None:
    token = issue_token(UserRole.AGENT)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve",
        json={},
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_list_queue_allowed_for_supervisor_role(
    client: TestClient, issue_token, monkeypatch
) -> None:
    async def fake_list_pending(self: ApprovalRequestRepository) -> list:
        return []

    monkeypatch.setattr(ApprovalRequestRepository, "list_pending", fake_list_pending)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.get("/supervisor/queue", headers=_auth_headers(token))
    assert response.status_code == 200


def test_list_queue_allowed_for_admin_role(client: TestClient, issue_token, monkeypatch) -> None:
    async def fake_list_pending(self: ApprovalRequestRepository) -> list:
        return []

    monkeypatch.setattr(ApprovalRequestRepository, "list_pending", fake_list_pending)

    token = issue_token(UserRole.ADMIN)
    response = client.get("/supervisor/queue", headers=_auth_headers(token))
    assert response.status_code == 200


# --- Queue listing / inspection ---


def test_list_queue_returns_pending_items(client: TestClient, issue_token, monkeypatch) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))

    async def fake_list_pending(self: ApprovalRequestRepository) -> list:
        return [item]

    monkeypatch.setattr(ApprovalRequestRepository, "list_pending", fake_list_pending)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.get("/supervisor/queue", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["ticket_id"] == _KNOWN_TICKET_ID
    assert body["items"][0]["selected_agent"] == "billing_agent"
    assert body["items"][0]["matched_policy_rules"] == ["refund"]


def test_get_queue_item_found(client: TestClient, issue_token, monkeypatch) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))

    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return item if ticket_id == uuid.UUID(_KNOWN_TICKET_ID) else None

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.get(f"/supervisor/queue/{_KNOWN_TICKET_ID}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["ticket_id"] == _KNOWN_TICKET_ID


def test_get_queue_item_not_found(client: TestClient, issue_token, monkeypatch) -> None:
    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return None

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.get(f"/supervisor/queue/{_UNKNOWN_TICKET_ID}", headers=_auth_headers(token))

    assert response.status_code == 404


def test_get_queue_item_logs_supervisor_viewed(
    client: TestClient, issue_token, monkeypatch, audit_events
) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))

    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return item

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)

    token = issue_token(UserRole.SUPERVISOR)
    client.get(f"/supervisor/queue/{_KNOWN_TICKET_ID}", headers=_auth_headers(token))

    assert len(audit_events) == 1
    assert audit_events[0]["event_type"] == "supervisor_viewed"
    assert audit_events[0]["ticket_id"] == uuid.UUID(_KNOWN_TICKET_ID)


# --- Approve / edit / reject ---


def test_approve_ticket_updates_status(client: TestClient, issue_token, monkeypatch) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))

    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return item

    async def fake_decide(self: ApprovalRequestRepository, **kwargs):
        item.status = kwargs["status"]
        item.approved_by = kwargs["reviewer_id"]
        item.comments = kwargs["comments"]
        return item

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)
    monkeypatch.setattr(ApprovalRequestRepository, "decide", fake_decide)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve",
        json={"comments": "looks good"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["comments"] == "looks good"


def test_approve_ticket_writes_audit_event(
    client: TestClient, issue_token, monkeypatch, audit_events
) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))

    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return item

    async def fake_decide(self: ApprovalRequestRepository, **kwargs):
        item.status = kwargs["status"]
        return item

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)
    monkeypatch.setattr(ApprovalRequestRepository, "decide", fake_decide)

    token = issue_token(UserRole.SUPERVISOR)
    client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve", json={}, headers=_auth_headers(token)
    )

    assert any(event["event_type"] == "supervisor_approved" for event in audit_events)


def test_edit_draft_updates_response(client: TestClient, issue_token, monkeypatch) -> None:
    item = build_approval_request(
        ticket_id=uuid.UUID(_KNOWN_TICKET_ID), draft_response="Original draft."
    )

    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return item

    async def fake_update_draft(self: ApprovalRequestRepository, **kwargs):
        item.draft_response = kwargs["draft_response"]
        return item

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)
    monkeypatch.setattr(ApprovalRequestRepository, "update_draft", fake_update_draft)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/edit",
        json={"draft_response": "Edited draft."},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["draft_response"] == "Edited draft."
    assert body["status"] == "pending"


def test_reject_ticket_marks_manual_review_status(
    client: TestClient, issue_token, monkeypatch
) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))

    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return item

    async def fake_decide(self: ApprovalRequestRepository, **kwargs):
        item.status = kwargs["status"]
        item.comments = kwargs["comments"]
        return item

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)
    monkeypatch.setattr(ApprovalRequestRepository, "decide", fake_decide)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject",
        json={"comments": "needs a human reply"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["comments"] == "needs a human reply"


def test_approve_unknown_ticket_returns_404(client: TestClient, issue_token, monkeypatch) -> None:
    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return None

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_UNKNOWN_TICKET_ID}/approve", json={}, headers=_auth_headers(token)
    )

    assert response.status_code == 404
