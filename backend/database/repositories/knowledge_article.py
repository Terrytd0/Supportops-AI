"""Repository for `KnowledgeArticle` reads.

Owns the only query CrewAI's knowledge-base tool
(`backend.tools.knowledge_base.KnowledgeBaseSearchTool`) needs: fetch every
article in a category, then rank by keyword overlap against the ticket text.
Ranking is a plain, DB-free function (`_rank_by_keyword_overlap`) so it's
unit-testable without a database connection, matching this repo's existing
pattern for deterministic logic (see `backend.policy.rules`).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.knowledge_article import KnowledgeArticle

_WORD_PATTERN = re.compile(r"[a-zA-Z']+")
_MIN_WORD_LENGTH = 3


def _keywords(text: str) -> set[str]:
    """Lowercase, deduplicated words of at least `_MIN_WORD_LENGTH` characters."""
    return {word for word in _WORD_PATTERN.findall(text.lower()) if len(word) >= _MIN_WORD_LENGTH}


def _rank_by_keyword_overlap(
    articles: list[KnowledgeArticle], query_text: str, limit: int
) -> list[KnowledgeArticle]:
    """Return up to `limit` articles, most keyword-relevant to `query_text` first.

    Falls back to `articles`' incoming (most-recent-first) order when no
    article's title/content shares a keyword with `query_text`, so
    category-relevant context is still returned rather than nothing.
    """
    if not articles:
        return []

    query_words = _keywords(query_text)

    def _score(article: KnowledgeArticle) -> int:
        haystack = _keywords(f"{article.title} {article.content}")
        return len(query_words & haystack)

    ranked = sorted(articles, key=_score, reverse=True)
    if _score(ranked[0]) == 0:
        return articles[:limit]
    return ranked[:limit]


class KnowledgeArticleRepository:
    """Read-only repository for the `knowledge_articles` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self, *, category: str, query_text: str, limit: int = 3
    ) -> list[KnowledgeArticle]:
        """Return up to `limit` articles in `category`, ranked by relevance to `query_text`."""
        stmt = (
            select(KnowledgeArticle)
            .where(KnowledgeArticle.category == category)
            .order_by(KnowledgeArticle.created_at.desc())
        )
        result = await self._session.execute(stmt)
        candidates = list(result.scalars().all())
        return _rank_by_keyword_overlap(candidates, query_text, limit)
