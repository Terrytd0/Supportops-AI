"""Repository for `Customer` reads.

`backend.services.ticket.create_ticket` uses `get_by_id` to validate
`customer_id` before creating a ticket, so a nonexistent customer surfaces
as a clean 404 instead of a raw PostgreSQL foreign-key-violation 500 (see
that module's `CustomerNotFound`). `list_all` backs `GET /customers`, the
easiest way to discover a valid `customer_id` for `POST /tickets` without
reading application logs or querying the database directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.customer import Customer


class CustomerRepository:
    """Read-only repository for the `customers` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        """Return `customer_id`'s `Customer`, or `None` if it doesn't exist."""
        return await self._session.get(Customer, customer_id)

    async def list_all(self, *, limit: int = 100) -> list[Customer]:
        """Return up to `limit` customers, most recently created first."""
        stmt = select(Customer).order_by(Customer.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
