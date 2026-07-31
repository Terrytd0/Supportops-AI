"""Ticket creation service: idempotency + persistence + the LangGraph workflow.

`create_ticket` is the one place that orchestrates all three -- exactly the
kind of multi-step use case `backend/services/README.md` calls out as
belonging here, rather than in `backend/api/routes/tickets.py` directly.

Flow: check/claim the idempotency key (fail closed -- see
`backend.services.idempotency`) -> create the `Ticket` row (Postgres, the
system of record) -> run the existing LangGraph workflow unchanged
(`backend.graph.workflow.get_graph`) -> store the response under the
idempotency key -> return it. A failure after claiming releases the claim
so a retry isn't blocked for the rest of the TTL.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from backend.config.settings import get_settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis_client
from backend.database.repositories.customer import CustomerRepository
from backend.database.repositories.ticket import TicketRepository
from backend.database.session import async_session_factory
from backend.graph.state import SupportAgentType, TicketCategory, WorkflowState, WorkflowStatus
from backend.graph.workflow import get_graph
from backend.schemas.ticket import TicketCreateRequest, TicketCreateResponse
from backend.services.idempotency import IdempotencyStore

logger = get_logger(__name__)


class TicketCreationInProgress(Exception):
    """Another request with the same idempotency key is still executing."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(f"Ticket creation for idempotency key {idempotency_key!r} is in progress")
        self.idempotency_key = idempotency_key


class CustomerNotFound(Exception):
    """`customer_id` doesn't reference an existing customer.

    Checked explicitly before the `Ticket` insert (see `_execute`) so this
    is what a nonexistent `customer_id` surfaces as -- not a raw PostgreSQL
    foreign-key-violation 500. `GET /customers`
    (`backend/api/routes/customers.py`) is how a caller finds a real one.
    """

    def __init__(self, customer_id: uuid.UUID) -> None:
        super().__init__(f"Customer {customer_id} not found")
        self.customer_id = customer_id


async def create_ticket(
    payload: TicketCreateRequest, idempotency_key: str | None
) -> TicketCreateResponse:
    """Create a ticket and run it through the support workflow.

    Raises `backend.services.idempotency.IdempotencyBackendUnavailable` if
    Redis can't be reached to check `idempotency_key` (the caller should
    turn that into a 503 -- see module docstring on why this fails closed),
    or `TicketCreationInProgress` if a concurrent request with the same key
    hasn't finished yet.
    """
    if idempotency_key is None:
        response = await _execute(payload)
        return response

    settings = get_settings()
    store = IdempotencyStore(get_redis_client(), ttl_seconds=settings.redis_idempotency_ttl_seconds)

    existing = await store.claim_or_get_existing(idempotency_key)
    if existing is not None:
        if existing.get("status") == "in_progress":
            raise TicketCreationInProgress(idempotency_key)
        logger.info(
            "Idempotent replay: returning original response",
            extra={"idempotency_key": idempotency_key},
        )
        return TicketCreateResponse(**{**existing, "idempotent_replay": True})

    try:
        response = await _execute(payload)
    except Exception:
        await store.release(idempotency_key)
        raise

    await store.complete(idempotency_key, response.model_dump(mode="json"))
    return response


async def _execute(payload: TicketCreateRequest) -> TicketCreateResponse:
    """Create the `Ticket` row, then run the unmodified LangGraph workflow.

    Raises `CustomerNotFound` if `payload.customer_id` doesn't reference a
    real customer -- checked explicitly, before the insert, so this is a
    clean error rather than a raw PostgreSQL foreign-key-violation 500.
    """
    async with async_session_factory() as session:
        customer = await CustomerRepository(session).get_by_id(payload.customer_id)
        if customer is None:
            raise CustomerNotFound(payload.customer_id)

        repository = TicketRepository(session)
        try:
            ticket = await repository.create(
                customer_id=payload.customer_id,
                subject=payload.subject,
                description=payload.description,
                priority=payload.priority,
            )
            await session.commit()
        except IntegrityError:
            # Defense in depth against a race between the check above and
            # this insert (e.g. the customer is removed concurrently) --
            # translate the same way as an upfront-missing customer rather
            # than let a raw foreign-key-violation 500 through either way.
            await session.rollback()
            raise CustomerNotFound(payload.customer_id) from None
        ticket_id = ticket.id
        created_at = ticket.created_at

    initial_state = WorkflowState(
        ticket_id=ticket_id,
        customer_id=payload.customer_id,
        ticket_text=f"{payload.subject}\n\n{payload.description}",
        workflow_status=WorkflowStatus.PENDING,
    )

    logger.info("Ticket %s created, starting workflow", ticket_id)
    # get_graph().invoke(...) is synchronous and makes blocking OpenAI/Postgres
    # calls; running it directly here would block the event loop this
    # (async) function runs on, so it's offloaded to a worker thread.
    final_state = await asyncio.to_thread(get_graph().invoke, initial_state)

    category: TicketCategory = final_state.get("category", TicketCategory.GENERAL)
    selected_agent: SupportAgentType = final_state.get(
        "selected_agent", SupportAgentType.GENERAL_AGENT
    )

    return TicketCreateResponse(
        ticket_id=ticket_id,
        customer_id=payload.customer_id,
        category=category.value,
        selected_agent=selected_agent.value,
        draft_response=final_state.get("draft_response", ""),
        requires_human_review=final_state.get("requires_human_review", False),
        matched_policy_rules=list(final_state.get("matched_policy_rules", ())),
        created_at=created_at if created_at is not None else datetime.now(UTC),
    )
