"""End-to-end integration test for `POST /tickets` against a real Redis.

Regression test for a real bug: `classify_ticket()` (and the checkpoint
store, and the knowledge-base tool) call `backend.core.redis_client.
get_redis_client()` from *inside* `backend.core.asyncio_utils.run_sync`,
which bridges from the plain worker thread `asyncio.to_thread(
get_graph().invoke, ...)` spawns (`backend.services.ticket._execute`) back
into async code. Before the fix, `run_sync`'s "no event loop running"
branch called a fresh `asyncio.run(coro)` on *every single call*, and
`get_redis_client()` was one process-wide `@lru_cache`d singleton --
meaning its connection pool got bound to whichever event loop first used it
(e.g. the main request-handling loop, via idempotency-key checking or rate
limiting) and then reused from a *different*, freshly-created loop the next
time a node in the worker thread touched it, raising
`RuntimeError: Future attached to a different loop` (or, on Windows,
`RuntimeError: Event loop is closed`) -- exactly the class of bug this test
exists to catch, since none of the fakeredis-backed unit tests exercise a
real, loop-affine `redis.asyncio.Redis` connection.

Only Postgres and OpenAI/CrewAI are faked here (no test-database harness
exists yet -- see `tests/integration/README.md`; `SpecialistAgent.respond`
is mocked the same way `tests/unit/graph/test_execute_agent_node.py` does,
since reaching the knowledge-base tool's own Redis cache would require a
real CrewAI/OpenAI tool-calling decision, which isn't deterministic to
test). Redis is real and unmocked -- see the `real_redis` fixture
(`tests/integration/conftest.py`), which skips this test if nothing is
listening on `localhost:6379`.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

import backend.graph.classifier as classifier
import backend.services.ticket as ticket_service
from backend.agents.base import AgentResult, SpecialistAgent
from backend.core.redis_client import get_redis_client
from backend.database.enums import CustomerTier, UserRole
from backend.database.models.customer import Customer
from backend.database.models.ticket import Ticket
from backend.graph.checkpoint import WorkflowCheckpointStore

pytestmark = pytest.mark.integration

_TICKET_TEXT = "My app keeps crashing on login."
_CUSTOMER_ID = uuid.uuid4()


class _NoOpSession:
    async def __aenter__(self) -> _NoOpSession:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def commit(self) -> None:
        pass


class _FakeCustomerRepository:
    def __init__(self, _session: object) -> None:
        pass

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        return Customer(
            id=customer_id,
            name="Jane Doe",
            email="jane.doe@example.com",
            company="Acme",
            tier=CustomerTier.STANDARD,
            created_at=datetime.now(UTC),
        )


class _FakeTicketRepository:
    def __init__(self, _session: object) -> None:
        pass

    async def create(self, **_kwargs: Any) -> Ticket:
        return Ticket(id=uuid.uuid4())


@pytest.fixture(autouse=True)
def _fake_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test-database harness exists yet (see `tests/integration/README.md`)
    -- only Redis is real in this test."""
    monkeypatch.setattr(ticket_service, "async_session_factory", lambda: _NoOpSession())
    monkeypatch.setattr(ticket_service, "CustomerRepository", _FakeCustomerRepository)
    monkeypatch.setattr(ticket_service, "TicketRepository", _FakeTicketRepository)


@pytest.fixture(autouse=True)
def _fake_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypasses real CrewAI/OpenAI, matching `test_execute_agent_node.py`'s
    convention -- `unresolved=False` and ticket text with no policy escalation
    keywords together keep `requires_human_review` False, so this test never
    touches the Postgres-backed supervisor-review path."""
    monkeypatch.setattr(
        SpecialistAgent,
        "respond",
        lambda self, ticket_text: AgentResult(
            response="We're looking into this.", retrieved_context="", unresolved=False
        ),
    )


class _FakeCompletions:
    """A `client.chat.completions` double returning a fixed classification.

    Constructing this at all proves classification was *not* served from
    cache -- used as a sentinel (`_NeverConstructedClient`, module-scope) to
    assert a cache hit skipped OpenAI entirely on the second request.
    """

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


class _NeverConstructedClient:
    def __init__(self, **_kwargs: Any) -> None:
        raise AssertionError(
            "OpenAI client should not be constructed -- classification should "
            "have been served from the real Redis cache"
        )


def _ticket_payload(customer_id: uuid.UUID = _CUSTOMER_ID) -> dict[str, Any]:
    return {
        "customer_id": str(customer_id),
        "subject": "App crash",
        "description": _TICKET_TEXT,
        "priority": "high",
    }


def _unique_idempotency_key() -> str:
    """A fresh key per call -- real Redis persists idempotency records for
    24h (`redis_idempotency_ttl_seconds`), so a fixed key would replay a
    prior test run's stored response across repeated suite runs instead of
    genuinely re-executing the workflow."""
    return f"integration-test-{uuid.uuid4()}"


def test_ticket_workflow_survives_the_main_loop_then_worker_thread_redis_sequence(
    real_redis: None,
    client: TestClient,
    issue_token,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact sequence that used to crash: an `Idempotency-Key` check
    touches the real Redis client directly on the app's own request-handling
    event loop *before* `asyncio.to_thread` hands the workflow to a plain
    worker thread, where `classify_ticket`'s cache lookup (via `run_sync`)
    touches the same `get_redis_client()` singleton again. Before the fix,
    this second touch crashed with "Future attached to a different loop"."""
    monkeypatch.setattr(classifier, "OpenAI", _FakeOpenAIClient)

    token = issue_token(UserRole.AGENT)
    with client:
        response = client.post(
            "/tickets",
            json=_ticket_payload(),
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": _unique_idempotency_key(),
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "general"
    assert body["requires_human_review"] is False


def test_repeated_ticket_text_is_served_from_the_real_redis_cache(
    real_redis: None,
    client: TestClient,
    issue_token,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second, independent ticket (different Idempotency-Key, so the
    workflow genuinely re-runs rather than replaying) with identical text
    must hit the real classification cache -- proving actual Redis
    round-trip behavior, not merely "didn't crash"."""
    monkeypatch.setattr(classifier, "OpenAI", _FakeOpenAIClient)
    token = issue_token(UserRole.AGENT)

    with client:
        first = client.post(
            "/tickets",
            json=_ticket_payload(),
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": _unique_idempotency_key(),
            },
        )
        assert first.status_code == 201

        # If classification were re-executed instead of served from cache,
        # constructing this client raises -- proving the second call's
        # `run_sync(cache.get(...))` genuinely round-tripped through Redis.
        monkeypatch.setattr(classifier, "OpenAI", _NeverConstructedClient)

        second = client.post(
            "/tickets",
            json=_ticket_payload(),
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": _unique_idempotency_key(),
            },
        )

    assert second.status_code == 201
    assert second.json()["category"] == first.json()["category"] == "general"


def test_workflow_checkpoints_are_actually_persisted_to_real_redis(
    real_redis: None,
    client: TestClient,
    issue_token,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checkpoint saves are best-effort (a failure is caught and logged, not
    raised -- see `backend.graph.nodes._checkpointed`), so a cross-loop crash
    there wouldn't fail the request. Read the checkpoint back from the real
    Redis directly to prove it was actually written, not silently dropped."""
    monkeypatch.setattr(classifier, "OpenAI", _FakeOpenAIClient)
    token = issue_token(UserRole.AGENT)

    with client:
        response = client.post(
            "/tickets",
            json=_ticket_payload(),
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": _unique_idempotency_key(),
            },
        )
    assert response.status_code == 201
    ticket_id = uuid.UUID(response.json()["ticket_id"])

    async def _read_checkpoint():
        store = WorkflowCheckpointStore(get_redis_client(), ttl_seconds=60)
        return await store.get_latest(ticket_id)

    checkpoint = asyncio.run(_read_checkpoint())

    assert checkpoint is not None
    assert checkpoint.stage == "policy_evaluation"
