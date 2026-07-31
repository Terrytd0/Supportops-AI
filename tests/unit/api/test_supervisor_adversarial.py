"""Adversarial-input tests for the supervisor approval-queue endpoints.

Complements `test_supervisor.py`'s happy-path/404/auth coverage with hostile
input at the HTTP boundary: malformed payloads, HTML/script and SQL-like
strings, an attempt to smuggle privilege-escalation fields into the request
body, and pathological (huge, non-ASCII) input -- verifying Pydantic
validation and JSON encoding handle all of it safely without executing,
interpreting, or crashing on any of it.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.database.enums import UserRole
from backend.database.repositories.approval_request import ApprovalRequestRepository
from tests.unit.api.conftest import build_approval_request

_KNOWN_TICKET_ID = "00000000-0000-0000-0000-000000000001"


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mock_approve_flow(monkeypatch, item) -> None:
    async def fake_get(self: ApprovalRequestRepository, ticket_id: uuid.UUID):
        return item

    async def fake_decide(self: ApprovalRequestRepository, **kwargs):
        item.status = kwargs["status"]
        item.comments = kwargs["comments"]
        return item

    monkeypatch.setattr(ApprovalRequestRepository, "get_by_ticket_id", fake_get)
    monkeypatch.setattr(ApprovalRequestRepository, "decide", fake_decide)


def test_malformed_ticket_id_returns_422(client: TestClient, issue_token) -> None:
    token = issue_token(UserRole.SUPERVISOR)
    response = client.get("/supervisor/queue/not-a-uuid", headers=_auth_headers(token))
    assert response.status_code == 422


def test_approve_with_wrong_field_type_returns_422(client: TestClient, issue_token) -> None:
    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve",
        json={"comments": 12345},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_approve_with_invalid_json_body_returns_422(client: TestClient, issue_token) -> None:
    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve",
        content=b"not json",
        headers={**_auth_headers(token), "content-type": "application/json"},
    )
    assert response.status_code == 422


def test_html_script_injection_in_comments_is_returned_verbatim_not_executed(
    client: TestClient, issue_token, monkeypatch
) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))
    _mock_approve_flow(monkeypatch, item)
    payload = "<script>alert('xss')</script>"

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve",
        json={"comments": payload},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["comments"] == payload


def test_sql_like_input_in_comments_is_handled_safely(
    client: TestClient, issue_token, monkeypatch
) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))
    _mock_approve_flow(monkeypatch, item)
    payload = "'; DROP TABLE tickets; --"

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve",
        json={"comments": payload},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["comments"] == payload


def test_embedded_role_escalation_fields_in_body_are_ignored(
    client: TestClient, issue_token, monkeypatch
) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))
    _mock_approve_flow(monkeypatch, item)

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/reject",
        json={"comments": "ok", "role": "admin", "is_admin": True, "status": "approved"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comments"] == "ok"
    assert body["status"] == "rejected"


def test_extremely_long_and_unicode_comment_is_accepted(
    client: TestClient, issue_token, monkeypatch
) -> None:
    item = build_approval_request(ticket_id=uuid.UUID(_KNOWN_TICKET_ID))
    _mock_approve_flow(monkeypatch, item)
    payload = ("refund me \U0001f4b0 " * 5_000) + "café résumé"

    token = issue_token(UserRole.SUPERVISOR)
    response = client.post(
        f"/supervisor/queue/{_KNOWN_TICKET_ID}/approve",
        json={"comments": payload},
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["comments"] == payload
