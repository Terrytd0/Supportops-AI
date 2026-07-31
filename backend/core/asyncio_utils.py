"""Sync/async bridge shared across the codebase's synchronous call sites.

Three call sites need this: `crewai.tools.BaseTool._run`
(`backend/tools/knowledge_base.py`), `backend/graph/nodes.py` (checkpoint
saves, `persist_results_node`), and `backend/graph/classifier.py`'s
classification cache -- all synchronous by contract (CrewAI's tool
interface; the LangGraph node-function convention), calling async
repository/service/Redis code. One implementation here, shared, rather than
each reinventing it.

Event-loop safety: `run_sync` always runs `coro` on one dedicated,
process-lifetime background event loop (started lazily, in its own daemon
thread) via `asyncio.run_coroutine_threadsafe` -- never via a fresh
`asyncio.run()` per call. This matters because
`asyncio.to_thread(get_graph().invoke, ...)`
(`backend.services.ticket._execute`) runs the *entire* LangGraph workflow in
one plain worker thread with no event loop of its own; every node's
`run_sync` call (checkpoints, classification cache, knowledge-base cache)
happens there, several times per ticket. A naive `asyncio.run(coro)` per
call would create *and close* a brand-new event loop on every single one of
those calls, and any `redis.asyncio` client whose connections got bound to
a previous (now-closed) loop would fail the next time it's reused --
"Future attached to a different loop" (or, on Windows' Proactor loop,
"Event loop is closed"). Routing every call through the same long-lived
loop instead means a client resolved *inside* a bridged coroutine (see
`backend.core.redis_client.get_redis_client`, which hands out one instance
per calling loop) is only ever touched by that one loop, for the life of
the process -- and its connection pool is actually reused across calls,
rather than reconnecting from scratch every time.

Callers must resolve any loop-affine resource (a Redis client, a database
session) *inside* the coroutine passed to `run_sync`, not before -- see
`backend.graph.classifier.classify_ticket` for the pattern. Resolving one
beforehand, in plain sync code, would bind it to whatever loop happened to
be running at that point (or none), defeating the guarantee above.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine


def _start_background_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, name="run-sync-bridge", daemon=True)
    thread.start()
    return loop


class _LazyBackgroundLoop:
    """Starts the shared background loop on first use, thread-safely.

    Several `asyncio.to_thread`-spawned LangGraph worker threads can call
    `run_sync` concurrently (concurrent `POST /tickets` requests), so the
    lazy-start itself must be safe under concurrent first use.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def get(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            with self._lock:
                if self._loop is None:
                    self._loop = _start_background_loop()
        return self._loop


_background_loop = _LazyBackgroundLoop()


def run_sync[T](coro: Coroutine[object, object, T]) -> T:
    """Run `coro` to completion from synchronous code.

    Always executes on the shared background loop (see module docstring),
    regardless of whether the calling thread has a running loop of its own
    -- safe to call from a plain thread (the common case: a LangGraph node
    running inside `asyncio.to_thread`) or from within another event loop
    (e.g. a test running under `pytest-asyncio`).
    """
    loop = _background_loop.get()

    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is loop:
        # coro was scheduled from a callback already executing on the
        # background loop itself -- blocking here for .result() would wait
        # forever on the very loop that needs to run it.
        coro.close()
        raise RuntimeError(
            "run_sync() cannot be called from a coroutine already running "
            "on run_sync's own background loop -- this would deadlock"
        )

    return asyncio.run_coroutine_threadsafe(coro, loop).result()
