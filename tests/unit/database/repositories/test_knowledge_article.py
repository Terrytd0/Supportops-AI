"""Unit tests for `KnowledgeArticleRepository`.

Uses a fake `AsyncSession` double (rather than a real database -- no test-DB
fixture exists yet, see `tests/unit/core/test_rate_limit.py`) so the
keyword-overlap ranking behavior is exercised without any DB connection.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models.knowledge_article import KnowledgeArticle
from backend.database.repositories.knowledge_article import KnowledgeArticleRepository


class _FakeScalars:
    def __init__(self, articles: list[KnowledgeArticle]) -> None:
        self._articles = articles

    def all(self) -> list[KnowledgeArticle]:
        return self._articles


class _FakeResult:
    def __init__(self, articles: list[KnowledgeArticle]) -> None:
        self._articles = articles

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._articles)


class _FakeSession:
    """Stands in for `AsyncSession`: returns canned articles regardless of the
    statement, so tests exercise `search()`'s ranking, not SQLAlchemy itself."""

    def __init__(self, articles: list[KnowledgeArticle]) -> None:
        self._articles = articles

    async def execute(self, _stmt: Any) -> _FakeResult:
        return _FakeResult(self._articles)


def _article(title: str, content: str, category: str = "billing") -> KnowledgeArticle:
    return KnowledgeArticle(category=category, title=title, content=content)


def _repository(*articles: KnowledgeArticle) -> KnowledgeArticleRepository:
    return KnowledgeArticleRepository(cast(AsyncSession, _FakeSession(list(articles))))


async def test_search_ranks_matching_article_first() -> None:
    unrelated = _article("Passwords", "Reset your login password.")
    refund_article = _article("Refunds", "How to request a refund for a duplicate charge.")
    repository = _repository(unrelated, refund_article)

    results = await repository.search(
        category="billing", query_text="I need a refund for a duplicate charge", limit=3
    )

    assert results[0] is refund_article


async def test_search_respects_limit() -> None:
    articles = [_article(f"Title {i}", f"Content {i}") for i in range(5)]
    repository = _repository(*articles)

    results = await repository.search(category="billing", query_text="anything", limit=2)

    assert len(results) == 2


async def test_search_returns_empty_list_when_no_articles_exist() -> None:
    repository = _repository()

    results = await repository.search(category="billing", query_text="refund", limit=3)

    assert results == []


async def test_search_falls_back_to_unranked_order_when_nothing_matches() -> None:
    articles = [_article("Alpha", "content one"), _article("Beta", "content two")]
    repository = _repository(*articles)

    results = await repository.search(
        category="billing", query_text="completely unrelated gibberish query", limit=2
    )

    assert results == articles
