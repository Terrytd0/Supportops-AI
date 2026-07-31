"""CrewAI tool exposing Postgres knowledge-base article search to agents.

Bridges CrewAI's synchronous tool-calling interface (`BaseTool._run`) to the
async `KnowledgeArticleRepository` via `backend.core.asyncio_utils.run_sync`,
so agent responses are grounded in real, retrieved support content instead of
relying on the LLM's own (unverifiable) knowledge -- see
`backend.agents.base.SpecialistAgent._retrieve_context`.

One tool instance is constructed per agent, bound to that agent's category
(`KnowledgeBaseSearchTool(category="billing")`, ...); only `query` is exposed
to the LLM's tool-calling schema, not `category`.

Redis supplements the knowledge base, it does not replace it: identical
(category, query) lookups are cached (`backend.core.cache.RedisCache`) so a
repeated question skips the Postgres round-trip, but a cache miss/failure
always falls through to the real repository query, never to an empty or
stale answer standing in for the knowledge base itself. Only a genuinely
successful search (results found, or legitimately none) is cached -- an
unavailable-lookup failure is not, so a transient outage doesn't get
semi-permanently cached as "no knowledge available" for the TTL.
"""

from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool

from backend.config.settings import get_settings
from backend.core.asyncio_utils import run_sync
from backend.core.cache import RedisCache, build_cache_key, normalize_text
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis_client
from backend.database.models.knowledge_article import KnowledgeArticle
from backend.database.repositories.knowledge_article import KnowledgeArticleRepository
from backend.database.session import async_session_factory

logger = get_logger(__name__)

_NO_RESULTS_MESSAGE = "No relevant knowledge-base articles were found."
_UNAVAILABLE_MESSAGE = "Knowledge-base lookup is unavailable right now."
_MAX_RESULTS = 3
_CACHE_KEY_PREFIX = "knowledge_base"


class KnowledgeBaseSearchTool(BaseTool):
    """Searches `knowledge_articles` for content relevant to a customer ticket."""

    name: str = "knowledge_base_search"
    description: str = (
        "Search the support knowledge base for articles relevant to a customer "
        "ticket. Always call this before answering so responses are grounded in "
        "documented support content rather than guessed."
    )
    category: str

    def _run(self, query: str) -> str:
        cache_key = build_cache_key(_CACHE_KEY_PREFIX, self.category, normalize_text(query))

        cached_result = run_sync(self._get_cached(cache_key))
        if isinstance(cached_result, str):
            logger.info("Knowledge base cache hit", extra={"category": self.category})
            return cached_result

        try:
            articles = run_sync(self._search(query))
        except Exception:
            logger.warning("Knowledge base search failed", extra={"category": self.category})
            return _UNAVAILABLE_MESSAGE

        if not articles:
            logger.info(
                "Knowledge base search returned no results",
                extra={"category": self.category},
            )
            run_sync(self._set_cached(cache_key, _NO_RESULTS_MESSAGE))
            return _NO_RESULTS_MESSAGE

        logger.info(
            "Knowledge base search returned %d article(s)",
            len(articles),
            extra={"category": self.category},
        )
        result = "\n\n".join(f"{article.title}: {article.content}" for article in articles)
        run_sync(self._set_cached(cache_key, result))
        return result

    async def _search(self, query: str) -> list[KnowledgeArticle]:
        async with async_session_factory() as session:
            repository = KnowledgeArticleRepository(session)
            return await repository.search(
                category=self.category, query_text=query, limit=_MAX_RESULTS
            )

    async def _get_cached(self, cache_key: str) -> Any | None:
        return await self._build_cache().get(cache_key)

    async def _set_cached(self, cache_key: str, value: str) -> None:
        await self._build_cache().set(cache_key, value)

    def _build_cache(self) -> RedisCache:
        """Resolve this call's Redis client and wrap it in a `RedisCache`.

        Must only be called from inside a coroutine passed to `run_sync`
        (i.e. from `_get_cached`/`_set_cached` above) -- `get_redis_client()`
        requires a running event loop, and must resolve to the loop
        `run_sync` actually runs on. See
        `backend/core/redis_client.py`'s module docstring.
        """
        settings = get_settings()
        return RedisCache(
            get_redis_client(),
            key_prefix=_CACHE_KEY_PREFIX,
            ttl_seconds=settings.redis_knowledge_cache_ttl_seconds,
        )
