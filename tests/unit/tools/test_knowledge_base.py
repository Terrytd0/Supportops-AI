"""Unit tests for `KnowledgeBaseSearchTool`.

`KnowledgeArticleRepository.search` is monkeypatched rather than a real
database connection (none is configured for tests -- see
`tests/unit/core/test_rate_limit.py`), so these exercise the tool's own
formatting, empty-result, failure-handling, and caching behavior, plus the
real sync/async bridge (`backend.core.asyncio_utils.run_sync`) end to end.
`get_redis_client` is monkeypatched to a shared `fakeredis.FakeAsyncRedis`
for every test (a real Redis connection attempt would otherwise cost
~0.4-0.5s per call).
"""

from __future__ import annotations

from typing import Any

import fakeredis
import pytest

import backend.tools.knowledge_base as knowledge_base
from backend.database.models.knowledge_article import KnowledgeArticle
from backend.database.repositories.knowledge_article import KnowledgeArticleRepository
from backend.tools.knowledge_base import (
    _NO_RESULTS_MESSAGE,
    _UNAVAILABLE_MESSAGE,
    KnowledgeBaseSearchTool,
)


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeAsyncRedis:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(knowledge_base, "get_redis_client", lambda: client)
    return client


def test_run_returns_formatted_articles_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    article = KnowledgeArticle(
        category="billing", title="Refund Policy", content="Refunds are issued within 5 days."
    )

    async def fake_search(self: KnowledgeArticleRepository, **_kwargs: object) -> list:
        return [article]

    monkeypatch.setattr(KnowledgeArticleRepository, "search", fake_search)

    tool = KnowledgeBaseSearchTool(category="billing")
    result = tool.run(query="when do refunds arrive")

    assert "Refund Policy" in result
    assert "Refunds are issued within 5 days." in result


def test_run_returns_no_results_message_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_search(self: KnowledgeArticleRepository, **_kwargs: object) -> list:
        return []

    monkeypatch.setattr(KnowledgeArticleRepository, "search", fake_search)

    tool = KnowledgeBaseSearchTool(category="technical")
    result = tool.run(query="anything")

    assert result == _NO_RESULTS_MESSAGE


def test_run_handles_repository_failure_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_search(self: KnowledgeArticleRepository, **_kwargs: object) -> list:
        raise RuntimeError("database is unreachable")

    monkeypatch.setattr(KnowledgeArticleRepository, "search", failing_search)

    tool = KnowledgeBaseSearchTool(category="account")
    result = tool.run(query="anything")

    assert result == _UNAVAILABLE_MESSAGE


def test_run_scopes_search_to_the_tool_s_category(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_categories: list[str] = []

    async def fake_search(self: KnowledgeArticleRepository, **kwargs: object) -> list:
        seen_categories.append(kwargs["category"])  # type: ignore[arg-type]
        return []

    monkeypatch.setattr(KnowledgeArticleRepository, "search", fake_search)

    KnowledgeBaseSearchTool(category="account").run(query="reset my permissions")

    assert seen_categories == ["account"]


def test_repeated_query_hits_the_cache_and_skips_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0
    article = KnowledgeArticle(
        category="billing", title="Refund Policy", content="Refunds are issued within 5 days."
    )

    async def fake_search(self: KnowledgeArticleRepository, **_kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        return [article]

    monkeypatch.setattr(KnowledgeArticleRepository, "search", fake_search)

    tool = KnowledgeBaseSearchTool(category="billing")
    first = tool.run(query="when do refunds arrive")
    second = tool.run(query="when do refunds arrive")

    assert call_count == 1
    assert first == second


def test_no_results_are_also_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """A legitimately empty result is a successful search, not a failure."""
    call_count = 0

    async def fake_search(self: KnowledgeArticleRepository, **_kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        return []

    monkeypatch.setattr(KnowledgeArticleRepository, "search", fake_search)

    tool = KnowledgeBaseSearchTool(category="technical")
    tool.run(query="anything")
    tool.run(query="anything")

    assert call_count == 1


def test_an_unavailable_lookup_is_not_cached(
    monkeypatch: pytest.MonkeyPatch, _fake_redis: fakeredis.FakeAsyncRedis
) -> None:
    """A transient outage must not get semi-permanently cached as "no
    knowledge available" for the TTL -- every call should retry."""
    call_count = 0

    async def failing_search(self: KnowledgeArticleRepository, **_kwargs: object) -> list:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("database is unreachable")

    monkeypatch.setattr(KnowledgeArticleRepository, "search", failing_search)

    tool = KnowledgeBaseSearchTool(category="account")
    tool.run(query="anything")
    tool.run(query="anything")

    assert call_count == 2


def test_cache_is_scoped_per_category(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same query text in two different categories must not collide."""
    seen: list[str] = []

    async def fake_search(self: KnowledgeArticleRepository, **kwargs: Any) -> list:
        seen.append(kwargs["category"])
        return []

    monkeypatch.setattr(KnowledgeArticleRepository, "search", fake_search)

    KnowledgeBaseSearchTool(category="billing").run(query="reset my password")
    KnowledgeBaseSearchTool(category="account").run(query="reset my password")

    assert seen == ["billing", "account"]
