"""ORM model for support knowledge-base articles.

Backs `backend.tools.knowledge_base.KnowledgeBaseSearchTool`: CrewAI
specialist agents (`backend/agents/`) retrieve grounded context from this
table via `backend.database.repositories.knowledge_article
.KnowledgeArticleRepository` instead of relying on the LLM's own
unverifiable, un-audited knowledge.

Not documented in docs/database_schema.md (that document predates this
sprint's agent work). `category` is a plain indexed string rather than a
`pg_enum` because its values are supplied by the agent layer (mirroring
`backend.graph.state.TicketCategory`), and per CLAUDE.md's layering rules
the database layer must not import from `backend.graph`.
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base, CreatedAtUpdatedAtMixin, UUIDPrimaryKeyMixin


class KnowledgeArticle(UUIDPrimaryKeyMixin, CreatedAtUpdatedAtMixin, Base):
    """A single support knowledge-base entry scoped to one ticket category."""

    __tablename__ = "knowledge_articles"

    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
