"""Customer lookup endpoint.

`GET /customers` is the easiest way to discover a valid `customer_id` for
`POST /tickets`: Swagger's auto-generated example UUID for
`TicketCreateRequest.customer_id` is never a real seeded customer, which
previously surfaced as an opaque 500 (a raw PostgreSQL foreign-key
violation) instead of a clear error -- see
`backend.services.ticket.CustomerNotFound`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth.dependencies import get_current_active_user
from backend.database.models.user import User
from backend.database.repositories.customer import CustomerRepository
from backend.database.session import async_session_factory
from backend.schemas.customer import CustomerListResponse, CustomerResponse

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    user: User = Depends(get_current_active_user),
) -> CustomerListResponse:
    """List known customers -- use one of these `customer_id` values for `POST /tickets`."""
    async with async_session_factory() as session:
        repository = CustomerRepository(session)
        customers = await repository.list_all()

    items = [
        CustomerResponse(
            customer_id=customer.id,
            name=customer.name,
            email=customer.email,
            company=customer.company,
            tier=customer.tier,
            created_at=customer.created_at,
        )
        for customer in customers
    ]
    return CustomerListResponse(items=items, total=len(items))
