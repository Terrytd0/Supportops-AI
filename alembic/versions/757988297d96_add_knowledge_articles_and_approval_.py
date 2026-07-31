"""add knowledge_articles and approval_request ai context columns

Revision ID: 757988297d96
Revises: 8f0d1bb0d4bb
Create Date: 2026-07-31 21:00:02.852445

Adds the two schema mismatches surfaced by the running app's logs:
"relation \"knowledge_articles\" does not exist" (the `KnowledgeArticle`
model, backing `backend.tools.knowledge_base.KnowledgeBaseSearchTool`, was
added without ever generating a migration for it) and "column
\"draft_response\" of relation \"approval_requests\" does not exist" (same
story for `ApprovalRequest`'s AI-execution-context columns --
`draft_response`, `retrieved_context`, `selected_agent`,
`matched_policy_rules` -- see that model's docstring). Autogenerate also
caught a third, related drift while diffing against the live database:
`approval_requests.requested_by` is `NOT NULL` in the database but
`nullable=True` on the model (`backend/database/models/approval_request.py`
explains why -- most rows are created automatically, with no human
`requested_by`), which would otherwise still block every
`_enqueue_supervisor_review` insert even after the two reported columns
exist.

The three new `NOT NULL` `approval_requests` columns (`draft_response`,
`selected_agent`, `matched_policy_rules`) get a temporary server-side
default so `ADD COLUMN` succeeds even if the table already has rows
("preserve existing data where practical"); the default is dropped again
once backfilled so the column's behavior matches the ORM model exactly
(no DB-side default -- every insert always supplies these explicitly, see
`ApprovalRequestRepository.create_pending`). `approval_requests` has zero
rows as of this migration (every insert attempt failed on the missing
columns first), so this is defense in depth, not a fix for actual data loss.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "757988297d96"
down_revision: str | None = "8f0d1bb0d4bb"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_articles",
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_articles")),
    )
    op.create_index(
        op.f("ix_knowledge_articles_category"), "knowledge_articles", ["category"], unique=False
    )

    op.add_column(
        "approval_requests",
        sa.Column("draft_response", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("approval_requests", sa.Column("retrieved_context", sa.Text(), nullable=True))
    op.add_column(
        "approval_requests",
        sa.Column("selected_agent", sa.String(length=50), nullable=False, server_default=""),
    )
    op.add_column(
        "approval_requests",
        sa.Column(
            "matched_policy_rules",
            sa.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    # Drop the temporary defaults now that any existing rows are backfilled --
    # the ORM model has no DB-side default for these (every insert supplies
    # them explicitly), so the column shouldn't silently have one either.
    op.alter_column("approval_requests", "draft_response", server_default=None)
    op.alter_column("approval_requests", "selected_agent", server_default=None)
    op.alter_column("approval_requests", "matched_policy_rules", server_default=None)

    op.alter_column(
        "approval_requests",
        "requested_by",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "approval_requests",
        "requested_by",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("approval_requests", "matched_policy_rules")
    op.drop_column("approval_requests", "selected_agent")
    op.drop_column("approval_requests", "retrieved_context")
    op.drop_column("approval_requests", "draft_response")
    op.drop_index(op.f("ix_knowledge_articles_category"), table_name="knowledge_articles")
    op.drop_table("knowledge_articles")
