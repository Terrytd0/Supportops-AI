# SupportOps AI

Enterprise-grade multi-agent customer support platform.

## Overview

SupportOps AI orchestrates a team of specialized AI agents (billing, technical,
account, and a General agent) to triage and resolve customer support
requests. Agent orchestration is built with **LangGraph** (stateful control flow)
and **CrewAI** (role-based agent collaboration), exposed via a **FastAPI**
backend, and backed by **PostgreSQL** (persistence) and **Redis** (caching /
short-term memory).

> Status: Sprint 4 scaffold. No business logic has been implemented yet — see
> `TODO` markers throughout the codebase and `docs/decisions.md` for what's
> pending.

## Tech Stack

- Python 3.12
- FastAPI
- LangGraph
- CrewAI
- PostgreSQL + SQLAlchemy + Alembic
- Redis
- Docker / Docker Compose
- GitHub Actions (CI)
- JWT / OAuth2 authentication
- Pytest

## Repository Layout

```
supportops-ai/
├── README.md
├── CLAUDE.md
├── LICENSE
├── .gitignore
├── .env.example
├── pyproject.toml
├── docker-compose.yml
│
├── docs/
│   ├── architecture.md
│   ├── business_requirements.md
│   ├── assumptions.md
│   ├── decisions.md
│   ├── design_review.md
│   └── adr/
│       └── ADR-001-langgraph-vs-crewai.md
│
├── backend/
│   ├── main.py                  # FastAPI application entry point
│   │
│   ├── api/
│   │   ├── routes/               # APIRouter modules (e.g. health)
│   │   ├── dependencies/         # FastAPI Depends providers (auth, db session, ...)
│   │   └── middleware/           # ASGI middleware (logging, correlation IDs, ...)
│   │
│   ├── agents/
│   │   ├── billing/               # Billing support agent
│   │   ├── technical/             # Technical support agent
│   │   ├── account/               # Account management agent
│   │   └── manager/                # General/supervisor agent (triage, routing, escalation)
│   │
│   ├── graph/                    # LangGraph state graph wiring agents together
│   ├── policy/                   # Routing, escalation, and guardrail business rules
│   ├── auth/                     # JWT/OAuth2 authentication & authorization
│   │
│   ├── database/
│   │   ├── models/                # SQLAlchemy declarative models
│   │   ├── migrations/            # Alembic migration environment
│   │   └── repositories/          # Repository-pattern data access
│   │
│   ├── services/                 # Application services (routes depend on these)
│   ├── tools/                    # Tool implementations exposed to agents
│   ├── schemas/                  # Pydantic request/response & internal contracts
│   └── config/                   # Settings (env-driven configuration)
│
├── tests/
│   ├── conftest.py
│   ├── unit/                     # Fast, isolated tests (mirrors backend/)
│   ├── integration/              # Tests against real Postgres/Redis
│   └── fixtures/                 # Shared fixtures, factories, sample data
│
├── docker/
│   └── Dockerfile
│
└── .github/
    └── workflows/
        └── ci.yml                # Lint + test CI pipeline (scaffold)
```

Every backend subpackage, `docs/`, `tests/`, and `docker/` folder has its own
`README.md` explaining its purpose in more detail — see the `README.md` inside
each subdirectory.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- [uv](https://github.com/astral-sh/uv) or `pip` for dependency management

### Local development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the API locally
uvicorn backend.main:app --reload

# Run the full stack (API + Postgres + Redis)
docker compose up --build
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
