"""Smoke tests for the placeholder supervisor queue endpoints."""

from fastapi.testclient import TestClient

_KNOWN_TICKET_ID = "00000000-0000-0000-0000-000000000001"
_UNKNOWN_TICKET_ID = "00000000-0000-0000-0000-000000009999"


def test_list_queue(client: TestClient) -> None:
    response = client.get("/supervisor/queue")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(body["items"])
    assert body["total"] >= 1


def test_get_queue_item_found(client: TestClient) -> None:
    response = client.get(f"/supervisor/queue/{_KNOWN_TICKET_ID}")
    assert response.status_code == 200
    assert response.json()["ticket_id"] == _KNOWN_TICKET_ID


def test_get_queue_item_not_found(client: TestClient) -> None:
    response = client.get(f"/supervisor/queue/{_UNKNOWN_TICKET_ID}")
    assert response.status_code == 404


def test_approve_ticket(client: TestClient) -> None:
    response = client.post(
        f"/supervisor/{_KNOWN_TICKET_ID}/approve", json={"comments": "looks good"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["comments"] == "looks good"


def test_reject_ticket(client: TestClient) -> None:
    response = client.post(f"/supervisor/{_KNOWN_TICKET_ID}/reject", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_approve_unknown_ticket_returns_404(client: TestClient) -> None:
    response = client.post(f"/supervisor/{_UNKNOWN_TICKET_ID}/approve", json={})
    assert response.status_code == 404
