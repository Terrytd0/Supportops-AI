"""ORM model for individual AI agent (LangGraph/CrewAI) execution runs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from backend.database.models.ticket import Ticket


class AgentRun(UUIDPrimaryKeyMixin, Base):
    """A single traced execution of an AI agent workflow for a ticket.

    docs/database_schema.md, "agent_runs" table. One row is written per
    LangGraph/CrewAI execution, capturing the model used, the full
    input/output payloads, latency, token usage, and outcome — this is
    what makes every AI execution traceable, per the schema's "Design
    Principles".
    """

    __tablename__ = "agent_runs"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_prompt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_completion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="agent_runs")
