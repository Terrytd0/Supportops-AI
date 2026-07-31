"""AI-powered ticket classification for `classify_ticket_node`.

This is deliberately *not* a CrewAI agent -- it's an internal orchestration
helper, used only by `backend.graph.nodes.classify_ticket_node`, that calls
OpenAI directly via structured outputs (`client.chat.completions.parse`
constrained to a `Literal` matching `TicketCategory`) rather than parsing
free-form text. It reuses the same `backend.config.settings` LLM
configuration as `backend/agents/`, never hardcoding a key or model name.

`classify_ticket` never raises: any failure (timeout, API error, malformed
response, an out-of-enum value) is logged as a warning and falls back to
`TicketCategory.GENERAL` -- the safe default that still routes the ticket to
a real specialist rather than crashing the workflow.

Identical ticket text is cached in Redis (`backend.core.cache.RedisCache`,
keyed by a normalized-text hash) so a repeated/duplicate ticket skips the
OpenAI call entirely. Only a *successful* classification is cached -- a
transient OpenAI failure must not get semi-permanently baked in as "this
exact wording is always GENERAL" for the cache's TTL.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel

from backend.config.settings import get_settings
from backend.core.asyncio_utils import run_sync
from backend.core.cache import RedisCache, build_cache_key, normalize_text
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis_client
from backend.graph.state import TicketCategory

logger = get_logger(__name__)

_CACHE_KEY_PREFIX = "classification"

_SYSTEM_PROMPT = (
    "You are a support ticket classifier. Assign exactly one category:\n"
    "- billing: invoices, refunds, subscriptions, pricing, payments, billing disputes\n"
    "- technical: bugs, crashes, API issues, login failures, troubleshooting, product issues\n"
    "- account: account settings, profile, permissions, user access, account management\n"
    "- general: anything that does not clearly belong to the categories above\n"
    "Choose the single best-fitting category for the ticket text you're given."
)


class _ClassificationResult(BaseModel):
    category: Literal["billing", "technical", "account", "general"]


def _build_cache() -> RedisCache:
    """Resolve this call's Redis client and wrap it in a `RedisCache`.

    Must only be called from inside a coroutine passed to `run_sync` (i.e.
    from inside `_get_cached`/`_set_cached` below), never from the plain
    sync body of `classify_ticket` itself -- `get_redis_client()` requires a
    running event loop, and calling it too early would bind the client to
    whatever loop happens to be running then (or none), rather than the one
    `run_sync` actually executes the coroutine on. See
    `backend/core/redis_client.py`'s module docstring.
    """
    settings = get_settings()
    return RedisCache(
        get_redis_client(),
        key_prefix=_CACHE_KEY_PREFIX,
        ttl_seconds=settings.redis_classification_cache_ttl_seconds,
    )


async def _get_cached(cache_key: str) -> Any | None:
    return await _build_cache().get(cache_key)


async def _set_cached(cache_key: str, value: str) -> None:
    await _build_cache().set(cache_key, value)


def classify_ticket(ticket_text: str) -> TicketCategory:
    """Classify `ticket_text` via an OpenAI structured-output call.

    Checks the Redis classification cache first (a miss, including any
    Redis failure, just proceeds to classify normally -- see `RedisCache`).
    Never raises -- any classification failure logs a warning and returns
    `TicketCategory.GENERAL` without touching the cache.
    """
    cache_key = build_cache_key(_CACHE_KEY_PREFIX, normalize_text(ticket_text))

    cached_value = run_sync(_get_cached(cache_key))
    if cached_value is not None:
        try:
            category = TicketCategory(cached_value)
        except ValueError:
            logger.warning("Ignoring invalid cached classification", extra={"value": cached_value})
        else:
            logger.info("Classification cache hit", extra={"category": category.value})
            return category

    settings = get_settings()
    client = OpenAI(
        api_key=settings.openai_api_key or None,
        timeout=settings.llm_request_timeout_seconds,
    )

    logger.info("Classification request starting")
    start = time.monotonic()
    try:
        completion = client.chat.completions.parse(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": ticket_text},
            ],
            response_format=_ClassificationResult,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("model returned no parsed classification")
        category = TicketCategory(parsed.category)
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.warning(
            "Classification failed, defaulting to GENERAL",
            extra={"error": str(exc), "duration_ms": duration_ms},
        )
        return TicketCategory.GENERAL

    duration_ms = round((time.monotonic() - start) * 1000, 1)
    logger.info(
        "Classification completed",
        extra={"category": category.value, "duration_ms": duration_ms},
    )
    run_sync(_set_cached(cache_key, category.value))
    return category
