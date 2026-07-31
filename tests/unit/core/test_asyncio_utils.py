"""Unit tests for the sync/async bridge shared by knowledge_base.py and nodes.py.

`run_sync` always executes on one dedicated, process-lifetime background
event loop (see the module docstring) rather than a fresh `asyncio.run()`
per call -- the tests below pin down that guarantee directly (same loop
object reused across calls, across threads, and safe under concurrent
first use), since it's exactly what a fresh-loop-per-call implementation
would get wrong and reintroduce the "Future attached to a different loop"
class of bug (see `tests/integration/test_ticket_workflow.py` for an
end-to-end reproduction against real Redis).
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from backend.core.asyncio_utils import run_sync


async def _return_value(value: str) -> str:
    return value


async def _current_loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_running_loop()


def test_run_sync_works_with_no_event_loop_running() -> None:
    """The common case: called from plain sync code (e.g. pytest's default
    sync test, or a synchronous CrewAI tool `_run`/LangGraph node)."""
    result = run_sync(_return_value("no loop"))

    assert result == "no loop"


async def test_run_sync_works_from_inside_a_running_event_loop() -> None:
    """`asyncio_mode = "auto"` runs this test inside its own event loop --
    a *different* loop from run_sync's background one, so this exercises
    the background loop being reached from within someone else's loop."""
    result = run_sync(_return_value("nested loop"))

    assert result == "nested loop"


def test_run_sync_propagates_exceptions() -> None:
    async def _raise() -> None:
        raise ValueError("boom")

    try:
        run_sync(_raise())
    except ValueError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("run_sync should have propagated the ValueError")


def test_run_sync_reuses_the_same_background_loop_across_calls() -> None:
    """The whole point: never create-and-close a new loop per call (that's
    exactly what breaks a loop-affine client like `redis.asyncio.Redis`
    across successive calls)."""
    first = run_sync(_current_loop())
    second = run_sync(_current_loop())

    assert first is second
    assert not first.is_closed()


def test_run_sync_reuses_the_same_background_loop_across_threads() -> None:
    """Several LangGraph worker threads (one per concurrent `POST /tickets`
    request, via `asyncio.to_thread`) must all land on the same background
    loop, not each get their own."""
    seen: list[asyncio.AbstractEventLoop] = []
    lock = threading.Lock()

    def worker() -> None:
        loop = run_sync(_current_loop())
        with lock:
            seen.append(loop)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == 5
    assert len({id(loop) for loop in seen}) == 1


def test_run_sync_from_the_background_loop_itself_raises_instead_of_deadlocking() -> None:
    """Defensive guard: a coroutine already running on run_sync's own
    background loop calling run_sync again would otherwise block forever
    waiting for that same loop to become free."""

    async def _call_run_sync_recursively() -> None:
        run_sync(_return_value("should not get here"))

    with pytest.raises(RuntimeError, match="deadlock"):
        run_sync(_call_run_sync_recursively())
