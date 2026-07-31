"""Regression test: the Alembic migration history must fully account for
every SQLAlchemy model.

This is the general form of the bug this project actually hit twice in a
row: `KnowledgeArticle` and `ApprovalRequest`'s AI-execution-context columns
were both added to `backend/database/models/` without ever generating a
migration for them, so the live database silently drifted out of sync with
the models -- surfacing at runtime as "relation ... does not exist" /
"column ... does not exist" (or, for a type-level drift, an asyncpg
`DataError`), never at review time. `alembic.autogenerate.compare_metadata`
is exactly Alembic's own "is there a pending migration?" check -- running it
here means a *future* model change without a matching migration fails this
test immediately instead of waiting to be discovered against a real
database, in production logs, the way these two were.

Needs a synchronous driver (`psycopg2-binary`, already a dependency) --
`compare_metadata`/`MigrationContext` don't speak SQLAlchemy's async engine.
Depends on the `real_postgres` fixture purely for its "skip if nothing is
listening on localhost:5432" behavior; the sync connection below is
independent of that fixture's (async-engine-only) monkeypatch.
"""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

# Registers every model on Base.metadata -- required for compare_metadata to
# know what the models actually look like.
import backend.database.models  # noqa: F401
from backend.database.base import Base

pytestmark = pytest.mark.integration


def test_models_match_the_database_schema_exactly(real_postgres: None) -> None:
    sync_url = "postgresql+psycopg2://supportops:supportops@localhost:5432/supportops_ai"
    engine = create_engine(sync_url)

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)

    engine.dispose()

    assert diff == [], (
        "The database schema no longer matches backend/database/models/ -- "
        f"generate a migration for this: {diff!r}"
    )
