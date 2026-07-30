# SupportOps AI

Enterprise-grade multi-agent customer support platform.

## Overview

SupportOps AI orchestrates a team of specialized AI agents (billing, technical,
account, and a General agent) to triage and resolve customer support
requests. Agent orchestration is built with **LangGraph** (stateful control flow)
and **CrewAI** (role-based agent collaboration), exposed via a **FastAPI**
backend, and backed by **PostgreSQL** (persistence) and **Redis** (caching /
short-term memory).

> Status: Sprint 4 scaffold. The LangGraph workflow orchestration backbone
> (`backend/graph/`), escalation policy (`backend/policy/`), and the
> supervisor approval-queue API (`backend/api/supervisor.py`) are implemented
> with deterministic placeholder logic; everything else is still `TODO` —
> see `TODO` markers throughout the codebase and `docs/decisions.md` for
> what's pending.

## Tech Stack

- Python 3.12
- FastAPI
- LangGraph
- CrewAI
- OpenAI (LLM provider, via `langchain-openai`)
- PostgreSQL + SQLAlchemy + Alembic
- Redis
- Docker / Docker Compose
- GitHub Actions (CI)
- JWT / OAuth2 authentication
- Pytest

## Current Features

- JWT/OAuth2 authentication
- LangGraph workflow orchestration
- CrewAI-ready agent architecture
- Policy-based escalation engine
- Supervisor approval workflow
- Audit logging
- PostgreSQL persistence layer
- Dockerized development environment
- Pytest test suite

## Authentication

SupportOps AI secures API endpoints using OAuth2 Password Flow with JWT 
authentication. Passwords are hashed with bcrypt, authenticated users are resolved
 through FastAPI dependencies, and the flow can be exercised through Swagger UI.

## Workflow Orchestration

The LangGraph workflow backbone (`backend/graph/`) compiles a fixed graph —
`load_ticket → classify_ticket → select_agent → execute_agent →
confidence_evaluation → persist_results` — with deterministic placeholder
logic in every node, ready for real classification, CrewAI agents, and
persistence to be dropped in without changing the topology.

![Compiled Workflow Graph](docs/screenshots/02-workflow.png)

## Supervisor Approval Queue

`confidence_evaluation_node` delegates human-review decisions to deterministic,
keyword-based escalation rules in `backend/policy/rules.py` (refund, legal,
lawsuit, attorney, security, breach, fraud, and low-confidence thresholds).
Tickets flagged for review surface through a placeholder supervisor queue API
(`backend/api/supervisor.py`):

- `GET /supervisor/queue` — list tickets pending approval
- `GET /supervisor/queue/{ticket_id}` — fetch a single queue entry
- `POST /supervisor/{ticket_id}/approve` — approve a ticket's draft response
- `POST /supervisor/{ticket_id}/reject` — reject a ticket's draft response

Every handler returns deterministic placeholder data today — no database
writes — with `TODO(Repository)` markers noting where `ApprovalRequestRepository`
calls will replace them.

## Repository Layout

```
supportops-ai/
├── README.md
├── CLAUDE.md
├── LICENSE
├── .gitignore
├── .env                          # Local environment overrides (git-ignored)
├── .env.example
├── pyproject.toml
├── docker-compose.yml
├── alembic.ini
│
├── alembic/                      # Alembic migration environment (async, targets Base.metadata)
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                 # Generated migration scripts
│
├── .github/
│   └── workflows/
│       └── ci.yml                # Lint + test CI pipeline (scaffold)
│
├── docs/
│   ├── architecture.md
│   ├── business_requirements.md
│   ├── assumptions.md
│   ├── database_schema.md
│   ├── decisions.md
│   ├── design_review.md
│   ├── adr/
│   │   └── ADR-001-langgraph-vs-crewai.md
│   │
│   └── screenshots/
│       ├── 01-authentication-flow.png
│       ├── 02-workflow.png
│       ├── 03-langgraph-smoke-test.png
│       └── 04-supervisor-api-smoke-test.png
│
├── backend/
│   ├── main.py                   # FastAPI application entry point
│   │
│   ├── api/
│   │   ├── README.md
│   │   ├── supervisor.py          # GET/POST /supervisor/... — placeholder approval-queue API
│   │   │
│   │   ├── routes/               # APIRouter modules (e.g. health)
│   │   │   └── health.py
│   │   │
│   │   ├── dependencies/         # FastAPI Depends providers (auth, db session, ...)
│   │   │
│   │   └── middleware/           # ASGI middleware (logging, correlation IDs, ...)
│   │
│   ├── agents/
│   │   ├── README.md
│   │   │
│   │   ├── billing/               # Billing support agent
│   │   │
│   │   ├── technical/             # Technical support agent
│   │   │
│   │   ├── account/               # Account management agent
│   │   │
│   │   └── general/               # General support agent
│   │
│   ├── graph/                     # LangGraph workflow orchestration backbone
│   │   ├── README.md
│   │   ├── state.py               # WorkflowState + TicketCategory/SupportAgentType/WorkflowStatus enums
│   │   ├── nodes.py                # load_ticket, classify_ticket, select_agent, execute_agent, confidence_evaluation, persist_results
│   │   └── workflow.py             # build_workflow() / get_graph() — compiles the node graph
│   │
│   ├── policy/                   # Routing, escalation, and guardrail business rules
│   │   ├── README.md
│   │   └── rules.py               # evaluate_policy() — keyword/threshold human-review escalation
│   │
│   ├── auth/                     # JWT/OAuth2 authentication & authorization
│   │   ├── README.md
│   │   ├── hashing.py             # Password hashing/verification (passlib/bcrypt)
│   │   ├── jwt.py                 # Access-token issuance & verification (python-jose)
│   │   ├── dependencies.py        # get_current_user, get_current_active_user, require_role
│   │   └── router.py              # POST /auth/login, GET /auth/me
│   │
│   ├── core/                     # Framework-level infra shared across the API
│   │   ├── README.md
│   │   ├── logging.py             # configure_logging(), get_logger() -- shared app logging
│   │   ├── rate_limit.py          # limiter, configure_rate_limiting() -- shared slowapi rate limiting
│   │   └── security.py            # OAuth2PasswordBearer scheme, 401/403 exceptions
│   │
│   ├── database/
│   │   ├── README.md
│   │   ├── base.py                # Declarative Base + UUID/timestamp mixins
│   │   ├── session.py             # Async engine + session factory
│   │   ├── enums.py               # UserRole, CustomerTier, TicketPriority/Status, ApprovalStatus
│   │   │
│   │   ├── models/                # SQLAlchemy declarative models
│   │   │   ├── user.py
│   │   │   ├── customer.py
│   │   │   ├── ticket.py
│   │   │   ├── agent_run.py
│   │   │   ├── approval_request.py
│   │   │   └── audit_log.py
│   │   │
│   │   ├── migrations/            # Alembic migration environment
│   │   │   └── README.md
│   │   │
│   │   └── repositories/          # Repository-pattern data access
│   │
│   ├── services/                 # Application services (routes depend on these)
│   │   ├── README.md
│   │   └── audit.py               # log_audit_event() — placeholder audit-logging call site
│   │
│   ├── tools/                    # Tool implementations exposed to agents
│   │   └── README.md
│   │
│   ├── schemas/                  # Pydantic request/response & internal contracts
│   │   ├── README.md
│   │   ├── auth.py                # Token, AuthenticatedUser
│   │   └── supervisor.py          # SupervisorQueueItem/Response, ApprovalDecisionRequest/Response
│   │
│   ├── config/                   # Settings (env-driven configuration)
│   │   ├── README.md
│   │   └── settings.py
│   │
│   └── scripts/                  # One-off scripts (python -m backend.scripts.<name>)
│       ├── README.md
│       ├── seed.py                # Idempotent dev-data seed (users, customers, tickets)
│       ├── run_workflow.py        # Runs the compiled LangGraph workflow against a sample ticket
│       ├── export_workflow.py     # Renders the compiled graph to workflow.png (Mermaid)
│       ├── load_test.py           # 50 concurrent requests against the running app; latency/throughput summary
│       ├── load_test_tickets.py   # Sample ticket payloads used by load_test.py
│       └── test_openai.py         # Manual OpenAI/langchain-openai connectivity smoke test
│
├── tests/
│   ├── README.md
│   ├── conftest.py
│   │
│   ├── unit/                     # Fast, isolated tests (mirrors backend/)
│   │   ├── README.md
│   │   ├── test_main.py
│   │   ├── api/
│   │   │   └── test_supervisor.py
│   │   │
│   │   ├── core/
│   │   │   ├── test_logging.py
│   │   │   └── test_rate_limit.py
│   │   │
│   │   ├── graph/
│   │   │   └── test_nodes.py
│   │   │
│   │   ├── policy/
│   │   │   └── test_rules.py
│   │   │
│   │   └── services/
│   │       └── test_audit.py
│   │
│   ├── integration/              # Tests against real Postgres/Redis
│   │   └── README.md
│   │
│   └── fixtures/                 # Shared fixtures, factories, sample data
│       └── README.md
│
└── docker/
    ├── Dockerfile
    └── README.md
```

Every backend subpackage, `docs/`, `tests/`, and `docker/` folder has its own
`README.md` explaining its purpose in more detail — see the `README.md` inside
each subdirectory.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose

### Local development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the API locally
uvicorn backend.main:app --reload

# Run the full stack (API + Postgres + Redis)
docker compose up --build
```

### Database migrations & seeding

```bash
# Apply migrations (schema)
alembic upgrade head

# Seed baseline dev data: 4 users, 5 demo customers, 15 demo tickets.
# Idempotent -- safe to run more than once.
python -m backend.scripts.seed
```

### Running the LangGraph workflow

```bash
# Runs the compiled workflow against a sample ticket and prints the final
# state. No LLM, database, or Redis required -- every node is a deterministic
# placeholder (see backend/graph/README.md).
python -m backend.scripts.run_workflow
```

### Running tests

```bash
pytest
```

## Documentation

- [Architecture](docs/architecture.md)
- [Business Requirements](docs/business_requirements.md)
- [Assumptions](docs/assumptions.md)
- [Decisions](docs/decisions.md)
- [Design Review](docs/design_review.md)
- [ADRs](docs/adr/)

## Project Conventions

See [CLAUDE.md](CLAUDE.md) for repository-specific engineering conventions and
guidance for AI-assisted development in this codebase.

## License

See [LICENSE](LICENSE).
