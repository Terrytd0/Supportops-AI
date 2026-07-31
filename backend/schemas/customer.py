"""Pydantic schemas for `GET /customers` (`backend/api/routes/customers.py`)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from backend.database.enums import CustomerTier


class CustomerResponse(BaseModel):
    """One customer -- `customer_id` is a valid `POST /tickets` `customer_id`."""

    customer_id: uuid.UUID
    name: str
    email: str
    company: str | None = None
    tier: CustomerTier
    created_at: datetime


class CustomerListResponse(BaseModel):
    """Response body for `GET /customers`."""

    items: list[CustomerResponse]
    total: int
