"""Tests for `POST /tickets`.

`backend.api.routes.tickets.create_ticket` (the service function, as
imported into the route module) is monkeypatched per test -- this file is
about the route's auth/status-code/error-translation behavior, not
idempotency itself (covered in `tests/unit/services/test_ticket.py`) or the
workflow (covered elsewhere).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import backend.api.routes.tickets as tickets_route
from backend.database.enums import UserRole
from backend.schemas.ticket import TicketCreateResponse
from backend.services.idempotency import IdempotencyBackendUnavailable
from backend.services.ticket import CustomerNotFound, TicketCreationInProgress

_VALID_PAYLOAD = {
    "customer_id": "00000000-0000-0000-0000-000000000101",
    "subject": "Billing issue",
    "description": "I was billed twice for my subscription.",
    "priority": "high",
}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fake_response(*, idempotent_replay: bool = False) -> TicketCreateResponse:
    return TicketCreateResponse(
        ticket_id=uuid.uuid4(),
        customer_id=uuid.UUID(_VALID_PAYLOAD["customer_id"]),
        category="billing",
        selected_agent="billing_agent",
        draft_response="Thanks for reaching out.",
        requires_human_review=False,
        matched_policy_rules=[],
        created_at=datetime.now(UTC),
        idempotent_replay=idempotent_replay,
    )


def test_create_ticket_without_a_token_is_401(client: TestClient) -> None:
    response = client.post("/tickets", json=_VALID_PAYLOAD)
    assert response.status_code == 401


def test_create_ticket_success_returns_201(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_create_ticket(payload, idempotency_key):  # type: ignore[no-untyped-def]
        return _fake_response()

    monkeypatch.setattr(tickets_route, "create_ticket", fake_create_ticket)

    token = issue_token(UserRole.AGENT)
    response = client.post(
        "/tickets",
        json=_VALID_PAYLOAD,
        headers={**_auth_headers(token), "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 201
    assert response.json()["category"] == "billing"
    assert response.json()["idempotent_replay"] is False


def test_create_ticket_replay_returns_200(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_create_ticket(payload, idempotency_key):  # type: ignore[no-untyped-def]
        return _fake_response(idempotent_replay=True)

    monkeypatch.setattr(tickets_route, "create_ticket", fake_create_ticket)

    token = issue_token(UserRole.AGENT)
    response = client.post(
        "/tickets",
        json=_VALID_PAYLOAD,
        headers={**_auth_headers(token), "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 200
    assert response.json()["idempotent_replay"] is True


def test_create_ticket_in_progress_returns_409(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_create_ticket(payload, idempotency_key):  # type: ignore[no-untyped-def]
        raise TicketCreationInProgress(idempotency_key or "key")

    monkeypatch.setattr(tickets_route, "create_ticket", fake_create_ticket)

    token = issue_token(UserRole.AGENT)
    response = client.post(
        "/tickets",
        json=_VALID_PAYLOAD,
        headers={**_auth_headers(token), "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 409


def test_create_ticket_redis_unavailable_returns_503(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_create_ticket(payload, idempotency_key):  # type: ignore[no-untyped-def]
        raise IdempotencyBackendUnavailable("connection refused")

    monkeypatch.setattr(tickets_route, "create_ticket", fake_create_ticket)

    token = issue_token(UserRole.AGENT)
    response = client.post(
        "/tickets",
        json=_VALID_PAYLOAD,
        headers={**_auth_headers(token), "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 503


def test_create_ticket_without_idempotency_key_is_accepted(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_create_ticket(payload, idempotency_key):  # type: ignore[no-untyped-def]
        assert idempotency_key is None
        return _fake_response()

    monkeypatch.setattr(tickets_route, "create_ticket", fake_create_ticket)

    token = issue_token(UserRole.AGENT)
    response = client.post("/tickets", json=_VALID_PAYLOAD, headers=_auth_headers(token))

    assert response.status_code == 201


def test_create_ticket_unknown_customer_returns_404(
    client: TestClient, issue_token, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_create_ticket(payload, idempotency_key):  # type: ignore[no-untyped-def]
        raise CustomerNotFound(uuid.UUID(_VALID_PAYLOAD["customer_id"]))

    monkeypatch.setattr(tickets_route, "create_ticket", fake_create_ticket)

    token = issue_token(UserRole.AGENT)
    response = client.post(
        "/tickets",
        json=_VALID_PAYLOAD,
        headers={**_auth_headers(token), "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_create_ticket_missing_required_field_returns_422(client: TestClient, issue_token) -> None:
    token = issue_token(UserRole.AGENT)
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "customer_id"}

    response = client.post("/tickets", json=payload, headers=_auth_headers(token))

    assert response.status_code == 422
