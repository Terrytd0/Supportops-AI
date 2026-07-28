"""ORM model for customers who submit support tickets."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from backend.database.enums import CustomerTier, pg_enum

if TYPE_CHECKING:
    from backend.database.models.ticket import Ticket


class Customer(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A company or individual that raises support tickets.

    docs/database_schema.md, "customers" table. Per "Cascade Rules",
    deleting a customer is prohibited while tickets exist — enforced via
    `ON DELETE RESTRICT` on `tickets.customer_id`.
    """

    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tier: Mapped[CustomerTier] = mapped_column(
        pg_enum(CustomerTier, "customer_tier"), nullable=False
    )

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="customer")
