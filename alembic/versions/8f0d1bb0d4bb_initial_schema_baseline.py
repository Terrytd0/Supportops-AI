"""Initial schema baseline (reconstructed).

Revision ID: 8f0d1bb0d4bb
Revises:
Create Date: 2026-07-31

This revision id was already stamped in `alembic_version` on every existing
deployment (dev, staging, ...) before its migration *file* was ever
committed to the repository -- the file was lost, but the schema it
produced was not: `agent_runs`, `approval_requests` (its original,
pre-AI-context shape), `audit_logs`, `customers`, `tickets`, and `users`
already existed for real. Rather than guess at exactly what the original
file looked like, this reconstructs it from the live schema itself
(`pg_dump --schema-only`, cross-checked against `backend/database/models/`
as they existed before the `KnowledgeArticle` model and `ApprovalRequest`'s
AI-execution-context columns were added), stamped with the *same* revision
id so it slots back into the existing history instead of creating a
parallel one. `alembic upgrade head` is a no-op on any database that
already has this schema (nothing here has actually changed); it only
matters for a *fresh* database that's never been migrated at all.

Statements run one at a time (`asyncpg` refuses multiple commands in a
single prepared statement, so one `op.execute()` per SQL statement rather
than one multi-statement string).

See `9c1a2f6e4b71_add_knowledge_articles_and_approval_.py` for the actual
delta this project needed: the `knowledge_articles` table and
`approval_requests`'s AI-execution-context columns, both added to the
SQLAlchemy models without a corresponding migration ever being generated --
see that revision's docstring for the full incident.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f0d1bb0d4bb"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_UPGRADE_STATEMENTS = (
    "CREATE TYPE public.approval_status AS ENUM ('pending', 'approved', 'rejected')",
    "CREATE TYPE public.customer_tier AS ENUM ('standard', 'premium', 'enterprise')",
    "CREATE TYPE public.ticket_priority AS ENUM ('low', 'medium', 'high', 'urgent')",
    """CREATE TYPE public.ticket_status AS ENUM (
        'new', 'triaged', 'assigned', 'drafted', 'approval_required',
        'approved', 'sent', 'closed'
    )""",
    "CREATE TYPE public.user_role AS ENUM ('agent', 'supervisor', 'admin')",
    """CREATE TABLE public.customers (
        id uuid NOT NULL,
        name character varying(255) NOT NULL,
        email character varying(255) NOT NULL,
        company character varying(255),
        tier public.customer_tier NOT NULL,
        created_at timestamp without time zone DEFAULT now() NOT NULL,
        CONSTRAINT pk_customers PRIMARY KEY (id)
    )""",
    "CREATE INDEX ix_customers_email ON public.customers USING btree (email)",
    "CREATE INDEX ix_customers_company ON public.customers USING btree (company)",
    """CREATE TABLE public.users (
        id uuid NOT NULL,
        email character varying(255) NOT NULL,
        password_hash text NOT NULL,
        full_name character varying(255) NOT NULL,
        role public.user_role NOT NULL,
        is_active boolean DEFAULT true NOT NULL,
        created_at timestamp without time zone DEFAULT now() NOT NULL,
        updated_at timestamp without time zone DEFAULT now() NOT NULL,
        CONSTRAINT pk_users PRIMARY KEY (id),
        CONSTRAINT uq_users_email UNIQUE (email)
    )""",
    """CREATE TABLE public.tickets (
        id uuid NOT NULL,
        customer_id uuid NOT NULL,
        assigned_agent_id uuid,
        subject character varying(255) NOT NULL,
        description text NOT NULL,
        priority public.ticket_priority NOT NULL,
        status public.ticket_status NOT NULL,
        ai_summary text,
        created_at timestamp without time zone DEFAULT now() NOT NULL,
        updated_at timestamp without time zone DEFAULT now() NOT NULL,
        CONSTRAINT pk_tickets PRIMARY KEY (id),
        CONSTRAINT fk_tickets_customer_id_customers
            FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE RESTRICT,
        CONSTRAINT fk_tickets_assigned_agent_id_users
            FOREIGN KEY (assigned_agent_id) REFERENCES public.users(id) ON DELETE RESTRICT
    )""",
    "CREATE INDEX ix_tickets_customer_id ON public.tickets USING btree (customer_id)",
    "CREATE INDEX ix_tickets_assigned_agent_id ON public.tickets USING btree (assigned_agent_id)",
    "CREATE INDEX ix_tickets_priority ON public.tickets USING btree (priority)",
    "CREATE INDEX ix_tickets_status ON public.tickets USING btree (status)",
    "CREATE INDEX ix_tickets_created_at ON public.tickets USING btree (created_at)",
    """CREATE TABLE public.approval_requests (
        id uuid NOT NULL,
        ticket_id uuid NOT NULL,
        requested_by uuid NOT NULL,
        approved_by uuid,
        status public.approval_status NOT NULL,
        comments text,
        requested_at timestamp without time zone DEFAULT now() NOT NULL,
        decided_at timestamp without time zone,
        CONSTRAINT pk_approval_requests PRIMARY KEY (id),
        CONSTRAINT fk_approval_requests_ticket_id_tickets
            FOREIGN KEY (ticket_id) REFERENCES public.tickets(id) ON DELETE RESTRICT,
        CONSTRAINT fk_approval_requests_requested_by_users
            FOREIGN KEY (requested_by) REFERENCES public.users(id) ON DELETE RESTRICT,
        CONSTRAINT fk_approval_requests_approved_by_users
            FOREIGN KEY (approved_by) REFERENCES public.users(id) ON DELETE RESTRICT
    )""",
    "CREATE INDEX ix_approval_requests_ticket_id "
    "ON public.approval_requests USING btree (ticket_id)",
    "CREATE INDEX ix_approval_requests_status ON public.approval_requests USING btree (status)",
    """CREATE TABLE public.audit_logs (
        id uuid NOT NULL,
        ticket_id uuid NOT NULL,
        user_id uuid,
        event_type character varying(100) NOT NULL,
        description text NOT NULL,
        metadata jsonb,
        created_at timestamp without time zone DEFAULT now() NOT NULL,
        CONSTRAINT pk_audit_logs PRIMARY KEY (id),
        CONSTRAINT fk_audit_logs_ticket_id_tickets
            FOREIGN KEY (ticket_id) REFERENCES public.tickets(id) ON DELETE RESTRICT,
        CONSTRAINT fk_audit_logs_user_id_users
            FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT
    )""",
    "CREATE INDEX ix_audit_logs_ticket_id ON public.audit_logs USING btree (ticket_id)",
    "CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at)",
    """CREATE TABLE public.agent_runs (
        id uuid NOT NULL,
        ticket_id uuid NOT NULL,
        agent_name character varying(100) NOT NULL,
        model character varying(100) NOT NULL,
        input jsonb NOT NULL,
        output jsonb NOT NULL,
        latency_ms integer NOT NULL,
        tokens_prompt integer,
        tokens_completion integer,
        success boolean NOT NULL,
        error_message text,
        created_at timestamp without time zone DEFAULT now() NOT NULL,
        CONSTRAINT pk_agent_runs PRIMARY KEY (id),
        CONSTRAINT fk_agent_runs_ticket_id_tickets
            FOREIGN KEY (ticket_id) REFERENCES public.tickets(id) ON DELETE RESTRICT
    )""",
    "CREATE INDEX ix_agent_runs_ticket_id ON public.agent_runs USING btree (ticket_id)",
    "CREATE INDEX ix_agent_runs_success ON public.agent_runs USING btree (success)",
    "CREATE INDEX ix_agent_runs_created_at ON public.agent_runs USING btree (created_at)",
)

_DOWNGRADE_STATEMENTS = (
    "DROP TABLE IF EXISTS public.agent_runs",
    "DROP TABLE IF EXISTS public.audit_logs",
    "DROP TABLE IF EXISTS public.approval_requests",
    "DROP TABLE IF EXISTS public.tickets",
    "DROP TABLE IF EXISTS public.users",
    "DROP TABLE IF EXISTS public.customers",
    "DROP TYPE IF EXISTS public.user_role",
    "DROP TYPE IF EXISTS public.ticket_status",
    "DROP TYPE IF EXISTS public.ticket_priority",
    "DROP TYPE IF EXISTS public.customer_tier",
    "DROP TYPE IF EXISTS public.approval_status",
)


def upgrade() -> None:
    for statement in _UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWNGRADE_STATEMENTS:
        op.execute(statement)
