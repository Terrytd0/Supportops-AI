"""Async SQLAlchemy engine and session factory.

Scope note: this module intentionally stops at the engine/session factory.
A FastAPI dependency that yields a request-scoped `AsyncSession` belongs to
a later milestone (see backend/database/README.md TODOs), once API routes
that actually need a database session exist.

Loop-scoped, not process-wide: mirrors `backend/core/redis_client.py`'s
design, for the identical reason. An `AsyncEngine`'s connection pool holds
asyncpg connections (and the asyncio primitives they use internally) bound
to whichever event loop first uses them; reusing one from a *different*
loop crashes -- most visibly via `pool_pre_ping=True`'s per-checkout health
check, which raises `RuntimeError: ... got Future ... attached to a
different loop` instead of the `OperationalError` it expects from a merely
dead connection, so the broken connection is never invalidated and keeps
failing every future checkout that lands on it (see
`backend/core/asyncio_utils.py`'s module docstring for the general
mechanism). This app runs two long-lived loops: FastAPI's own
request-handling loop (used directly by most routes/services, e.g.
`backend.auth.dependencies.get_current_user`, `backend.services.ticket.
_execute`) and `run_sync`'s dedicated background loop (used by
`backend.graph.nodes._enqueue_supervisor_review` and
`backend.tools.knowledge_base.KnowledgeBaseSearchTool._search`, both
bridged from LangGraph's synchronous node functions). `async_session_factory()`
therefore resolves a loop-scoped engine/session-factory pair rather than
sharing one process-wide singleton across both.
"""

from __future__ import annotations

import asyncio
import weakref

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config.settings import get_settings

_session_factories_by_loop: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, async_sessionmaker[AsyncSession]
] = weakref.WeakKeyDictionary()


def _build_session_factory() -> async_sessionmaker[AsyncSession]:
    settings = get_settings()
    # `pool_pre_ping` avoids handing out stale connections after e.g. a
    # database restart or an idle timeout closing them out from under the
    # pool.
    engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
    # `expire_on_commit=False` so ORM instances remain usable after `commit()`
    # without triggering an implicit (and, in async SQLAlchemy, unsafe) lazy
    # reload -- the standard recommendation for `AsyncSession`.
    return async_sessionmaker(bind=engine, expire_on_commit=False)


def async_session_factory() -> AsyncSession:
    """Return a new `AsyncSession` bound to the calling event loop's engine.

    Kept as a plain function (rather than a pre-built `async_sessionmaker`
    instance) so every existing call site's
    `async with async_session_factory() as session:` keeps working
    unchanged, while the engine/session factory it resolves is now
    loop-scoped -- see the module docstring. Must be called from inside a
    running event loop (raises `RuntimeError` via `asyncio.get_running_loop()`
    otherwise), same requirement as `backend.core.redis_client.get_redis_client`.
    """
    loop = asyncio.get_running_loop()
    factory = _session_factories_by_loop.get(loop)
    if factory is None:
        factory = _build_session_factory()
        _session_factories_by_loop[loop] = factory
    return factory()
