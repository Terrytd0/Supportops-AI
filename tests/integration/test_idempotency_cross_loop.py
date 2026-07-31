"""Regression test: `POST /tickets` must succeed the same way whether or not
an `Idempotency-Key` header is supplied.

Root cause this guards against: `backend/database/session.py`'s
`AsyncEngine`/session factory was a single process-wide singleton, shared
between two long-lived event loops -- FastAPI's own request-handling loop
(used directly by e.g. `backend.auth.dependencies.get_current_user`,
`backend.services.ticket._execute`'s customer/ticket writes) and
`backend.core.asyncio_utils.run_sync`'s dedicated background loop (used by
`backend.graph.nodes._enqueue_supervisor_review`, which only runs when
`requires_human_review` is set). A connection established on one loop and
later checked out on the other crashed `pool_pre_ping`'s per-checkout health
check with `RuntimeError: ... got Future ... attached to a different loop`
-- and because that's a raw `RuntimeError`, not the `OperationalError`
SQLAlchemy expects from a merely-dead connection, the broken connection was
never invalidated and kept failing *every* future checkout that landed on
it, essentially at random (whichever request's turn it was to receive that
particular pooled connection) -- with or without an `Idempotency-Key`. A
narrow investigation of only the idempotency code path would not have found
this: reproducing it against real infrastructure (see `real_postgres`,
`real_redis` in `conftest.py`) is what surfaced it, since no unit test's
mocked `AsyncSession`/Redis double has real, loop-affine connections to get
this wrong with.

Fixed the same way `backend/core/redis_client.py` already was: the session
factory hands out one engine per *calling* event loop instead of one for
the whole process (see `backend/database/session.py`'s module docstring).

`SpecialistAgent.respond` is stubbed to always report `unresolved=True`,
guaranteeing `requires_human_review` (so every ticket created here exercises
`_enqueue_supervisor_review`'s real, background-loop Postgres write) --
without that, this test could pass or fail depending on unrelated CrewAI/
policy behavior instead of deterministically exercising the two-loop path.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

import backend.graph.classifier as classifier
from backend.agents.base import AgentResult, SpecialistAgent
from backend.database.enums import UserRole

pytestmark = pytest.mark.integration

_TICKET_TEXT = "My app keeps crashing on login."


class _FakeCompletions:
    def parse(self, **_kwargs: Any) -> Any:
        from dataclasses import dataclass

        @dataclass
        class _Parsed:
            category: str = "general"

        @dataclass
        class _Message:
            parsed: _Parsed

        @dataclass
        class _Choice:
            message: _Message

        @dataclass
        class _Completion:
            choices: list[_Choice]

        return _Completion(choices=[_Choice(_Message(_Parsed()))])


class _FakeOpenAIClient:
    def __init__(self, **_kwargs: Any) -> None:
        self.chat = type("_Chat", (), {"completions": _FakeCompletions()})()


@pytest.fixture(autouse=True)
def _fake_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(classifier, "OpenAI", _FakeOpenAIClient)


@pytest.fixture(autouse=True)
def _fake_agent_always_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forces `requires_human_review=True` on every ticket (no keyword match
    needed), so `_enqueue_supervisor_review`'s real Postgres write -- on
    `run_sync`'s background loop -- runs every single time."""
    monkeypatch.setattr(
        SpecialistAgent,
        "respond",
        lambda self, ticket_text: AgentResult(
            response="We're looking into this.", retrieved_context="", unresolved=True
        ),
    )


def _payload(customer_id: uuid.UUID) -> dict[str, Any]:
    return {
        "customer_id": str(customer_id),
        "subject": "App crash",
        "description": _TICKET_TEXT,
        "priority": "high",
    }


def _post(
    client: TestClient, token: str, customer_id: uuid.UUID, idempotency_key: str | None
) -> Any:
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return client.post("/tickets", json=_payload(customer_id), headers=headers)


def test_repeated_requests_without_idempotency_key_all_succeed(
    real_redis: None,
    real_customer: uuid.UUID,
    client: TestClient,
    issue_token,
) -> None:
    token = issue_token(UserRole.AGENT)

    with client:
        responses = [_post(client, token, real_customer, None) for _ in range(4)]

    assert [r.status_code for r in responses] == [201, 201, 201, 201]
    ticket_ids = {r.json()["ticket_id"] for r in responses}
    assert len(ticket_ids) == 4, "each call with no key should create a distinct ticket"


def test_repeated_requests_with_unique_idempotency_keys_all_succeed(
    real_redis: None,
    real_customer: uuid.UUID,
    client: TestClient,
    issue_token,
) -> None:
    token = issue_token(UserRole.AGENT)

    with client:
        responses = [
            _post(client, token, real_customer, f"cross-loop-key-{uuid.uuid4()}") for _ in range(4)
        ]

    assert [r.status_code for r in responses] == [201, 201, 201, 201]
    ticket_ids = {r.json()["ticket_id"] for r in responses}
    assert len(ticket_ids) == 4, "each call with a distinct key should create a distinct ticket"


def test_with_and_without_idempotency_key_interleaved_all_succeed(
    real_redis: None,
    real_customer: uuid.UUID,
    client: TestClient,
    issue_token,
) -> None:
    """The exact sequence originally reported: some requests with no key,
    some with one, back to back -- neither should ever 500."""
    token = issue_token(UserRole.AGENT)
    keys: list[str | None] = [
        None,
        f"cross-loop-key-{uuid.uuid4()}",
        None,
        f"cross-loop-key-{uuid.uuid4()}",
    ]

    with client:
        responses = [_post(client, token, real_customer, key) for key in keys]

    assert [r.status_code for r in responses] == [201, 201, 201, 201]


def test_replaying_the_same_idempotency_key_succeeds_without_rerunning_the_workflow(
    real_redis: None,
    real_customer: uuid.UUID,
    client: TestClient,
    issue_token,
) -> None:
    token = issue_token(UserRole.AGENT)
    key = f"cross-loop-key-{uuid.uuid4()}"

    with client:
        first = _post(client, token, real_customer, key)
        second = _post(client, token, real_customer, key)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert second.json()["idempotent_replay"] is True
    assert second.json()["ticket_id"] == first.json()["ticket_id"]
