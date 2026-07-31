"""Unit tests for `classify_ticket`'s OpenAI structured-output classification
and its Redis classification cache.

`OpenAI` (the SDK client class) is monkeypatched to a fake exposing exactly
the shape `classify_ticket` calls (`client.chat.completions.parse(...)` ->
`.choices[0].message.parsed.category`) -- never a real network call, and
never asserting on exact LLM wording since there isn't any: only the
resulting `TicketCategory` is checked. `get_redis_client` is monkeypatched
to a shared `fakeredis.FakeAsyncRedis` for every test in this module (a real
Redis connection attempt would otherwise cost ~0.4-0.5s per call -- see
`backend/core/redis_client.py`'s connect timeout).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import fakeredis
import pytest

import backend.graph.classifier as classifier
from backend.graph.state import TicketCategory


@dataclass
class _FakeParsed:
    category: str


class _FakeMessage:
    def __init__(self, parsed: _FakeParsed | None) -> None:
        self.parsed = parsed


class _FakeChoice:
    def __init__(self, parsed: _FakeParsed | None) -> None:
        self.message = _FakeMessage(parsed)


class _FakeCompletion:
    def __init__(self, parsed: _FakeParsed | None) -> None:
        self.choices = [_FakeChoice(parsed)]


class _FakeCompletions:
    def __init__(
        self, *, parsed: _FakeParsed | None = None, raises: Exception | None = None
    ) -> None:
        self._parsed = parsed
        self._raises = raises

    def parse(self, **_kwargs: Any) -> _FakeCompletion:
        if self._raises is not None:
            raise self._raises
        return _FakeCompletion(self._parsed)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeOpenAIClient:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = _FakeChat(completions)


class _NeverCalledOpenAIClient:
    """Used to prove a cache hit never reaches the OpenAI call at all."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("OpenAI client should not be constructed on a cache hit")


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeAsyncRedis:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(classifier, "get_redis_client", lambda: client)
    return client


def _patch_openai_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    parsed: _FakeParsed | None = None,
    raises: Exception | None = None,
) -> None:
    completions = _FakeCompletions(parsed=parsed, raises=raises)
    monkeypatch.setattr(classifier, "OpenAI", lambda **_kwargs: _FakeOpenAIClient(completions))


@pytest.mark.parametrize(
    ("ticket_text", "category", "expected"),
    [
        ("Invoice charged twice", "billing", TicketCategory.BILLING),
        ("Application freezes after login", "technical", TicketCategory.TECHNICAL),
        ("Need to change account permissions", "account", TicketCategory.ACCOUNT),
        ("What are your business hours?", "general", TicketCategory.GENERAL),
    ],
)
def test_classify_ticket_returns_expected_category(
    monkeypatch: pytest.MonkeyPatch, ticket_text: str, category: str, expected: TicketCategory
) -> None:
    _patch_openai_client(monkeypatch, parsed=_FakeParsed(category=category))

    assert classifier.classify_ticket(ticket_text) is expected


def test_classify_ticket_defaults_to_general_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_openai_client(monkeypatch, raises=TimeoutError("request timed out"))

    assert classifier.classify_ticket("Anything at all.") is TicketCategory.GENERAL


def test_classify_ticket_defaults_to_general_on_malformed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`message.parsed is None` -- the SDK's own signal that structured
    parsing failed."""
    _patch_openai_client(monkeypatch, parsed=None)

    assert classifier.classify_ticket("Anything at all.") is TicketCategory.GENERAL


def test_classify_ticket_defaults_to_general_on_invalid_enum_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `category` outside the four known values must not propagate as a
    crash or an invalid `TicketCategory`."""
    _patch_openai_client(monkeypatch, parsed=_FakeParsed(category="not_a_real_category"))

    assert classifier.classify_ticket("Anything at all.") is TicketCategory.GENERAL


def test_classify_ticket_defaults_to_general_on_generic_api_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_openai_client(monkeypatch, raises=RuntimeError("OpenAI API error"))

    assert classifier.classify_ticket("Anything at all.") is TicketCategory.GENERAL


def test_repeated_ticket_text_hits_the_cache_and_skips_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_openai_client(monkeypatch, parsed=_FakeParsed(category="billing"))

    first = classifier.classify_ticket("Invoice charged twice")
    assert first is TicketCategory.BILLING

    # If a second call reached OpenAI again, constructing this client raises.
    monkeypatch.setattr(classifier, "OpenAI", _NeverCalledOpenAIClient)
    second = classifier.classify_ticket("Invoice charged twice")

    assert second is TicketCategory.BILLING


def test_cache_is_keyed_by_normalized_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trivially different whitespace/casing still hits the same cache entry."""
    _patch_openai_client(monkeypatch, parsed=_FakeParsed(category="billing"))

    classifier.classify_ticket("Invoice charged twice")

    monkeypatch.setattr(classifier, "OpenAI", _NeverCalledOpenAIClient)
    result = classifier.classify_ticket("  INVOICE   charged twice  ")

    assert result is TicketCategory.BILLING


async def test_a_failed_classification_is_not_cached(
    monkeypatch: pytest.MonkeyPatch, _fake_redis: fakeredis.FakeAsyncRedis
) -> None:
    """A transient OpenAI failure must not get semi-permanently baked in as
    "this exact wording is always GENERAL" for the cache's TTL."""
    _patch_openai_client(monkeypatch, raises=RuntimeError("boom"))

    classifier.classify_ticket("Invoice charged twice")

    cache = classifier._build_cache()
    key = cache.build_key(classifier.normalize_text("Invoice charged twice"))
    assert await cache.get(key) is None
