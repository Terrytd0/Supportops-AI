"""Ticket creation endpoint: idempotent, runs the full support workflow.

`POST /tickets` is the first real entry point into
`backend.graph.workflow.get_graph()` -- previously only exercised via
`python -m backend.scripts.run_workflow`. Clients supply an
`Idempotency-Key` header to make retries (e.g. after a timeout) safe:
duplicate ticket creation must never occur, so a request replayed with the
same key gets back the original response rather than creating a second
ticket -- see `backend/services/idempotency.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from backend.auth.dependencies import get_current_active_user
from backend.core.logging import get_logger
from backend.core.rate_limit import limiter
from backend.database.models.user import User
from backend.schemas.ticket import TicketCreateRequest, TicketCreateResponse
from backend.services.idempotency import IdempotencyBackendUnavailable
from backend.services.ticket import CustomerNotFound, TicketCreationInProgress, create_ticket

logger = get_logger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])

# Looser than login, tighter than read-only queue endpoints: each call runs
# the full OpenAI/CrewAI workflow, a meaningfully more expensive operation
# than the routes elsewhere in the app.
_TICKET_CREATION_RATE_LIMIT = "10/minute"


@router.post(
    "",
    response_model=TicketCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(_TICKET_CREATION_RATE_LIMIT)
async def create_ticket_endpoint(
    request: Request,
    response: Response,
    payload: TicketCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_active_user),
) -> TicketCreateResponse:
    """Create a ticket and run it through classification, specialist
    response generation, and policy evaluation."""
    try:
        ticket_response = await create_ticket(payload, idempotency_key)
    except TicketCreationInProgress as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A request with this Idempotency-Key is already being processed",
        ) from exc
    except IdempotencyBackendUnavailable as exc:
        logger.error("Idempotency backend unavailable", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify request idempotency right now; please retry",
        ) from exc
    except CustomerNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Customer {exc.customer_id} not found. "
                "See GET /customers for valid customer_id values."
            ),
        ) from exc

    if ticket_response.idempotent_replay:
        # Nothing was created this time -- 200 rather than the route's
        # default 201, mirroring how e.g. Stripe's idempotency keys work.
        response.status_code = status.HTTP_200_OK
    return ticket_response
