"""Async SQLAlchemy engine and session factory.

Scope note: this module intentionally stops at the engine/session factory.
A FastAPI dependency that yields a request-scoped `AsyncSession` belongs to
a later milestone (see backend/database/README.md TODOs), once API routes
that actually need a database session exist.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config.settings import get_settings

settings = get_settings()

# `pool_pre_ping` avoids handing out stale connections after e.g. a database
# restart or an idle timeout closing them out from under the pool.
engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)

# `expire_on_commit=False` so ORM instances remain usable after `commit()`
# without triggering an implicit (and, in async SQLAlchemy, unsafe) lazy
# reload — the standard recommendation for `AsyncSession`.
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)
