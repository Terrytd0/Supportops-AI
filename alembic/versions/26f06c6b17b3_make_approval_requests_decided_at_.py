"""make approval_requests decided_at timezone aware

Revision ID: 26f06c6b17b3
Revises: 757988297d96
Create Date: 2026-07-31 21:19:30.556895

Surfaced while demonstrating the supervisor queue end-to-end after the
previous migration: `POST /supervisor/queue/{id}/approve` 500'd with
asyncpg's "can't subtract offset-naive and offset-aware datetimes", because
`ApprovalRequestRepository.decide` sets `decided_at = datetime.now(UTC)` (a
timezone-aware value) into what was a `TIMESTAMP WITHOUT TIME ZONE` column
-- every other timestamp column here is a DB-side `server_default=func.now()`
never touched from Python, so none of them share this bug (see
`backend/database/models/approval_request.py`).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26f06c6b17b3"
down_revision: str | None = "757988297d96"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "approval_requests",
        "decided_at",
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "approval_requests",
        "decided_at",
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
    )
