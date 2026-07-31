# SupportOps AI

Enterprise-grade multi-agent customer support platform.

## Overview

SupportOps AI orchestrates a team of specialized AI agents (billing, technical,
account, and a General agent) to triage and resolve customer support
requests. Agent orchestration is built with **LangGraph** (stateful control flow)
and **CrewAI** (role-based agent collaboration), exposed via a **FastAPI**
backend. **PostgreSQL** is the system of record for all business data;
**Redis** provides ephemeral infrastructure -- distributed rate limiting,
idempotent ticket creation, LangGraph workflow checkpoints, and AI/knowledge
caching -- see "Redis: Ephemeral Infrastructure" below.

> Status: `classify_ticket_node` (OpenAI structured-output classification),
> `execute_agent_node` (real CrewAI specialist agents), the policy engine,
> and the supervisor approval queue (a real Postgres-backed workflow, not a
> placeholder) are fully implemented. `POST /tickets` is the first real
> entry point into the LangGraph workflow. Remaining gaps are tracked as
> `TODO` markers throughout the codebase and in `docs/decisions.md`.

## Tech Stack

- Python 3.12+
- FastAPI
- LangGraph
- CrewAI
- OpenAI (LLM provider, via `langchain-openai`)
- PostgreSQL + SQLAlchemy + Alembic (system of record)
- Redis (rate limiting, idempotency, workflow checkpoints, AI/knowledge caches)
- Docker / Docker Compose
- GitHub Actions (CI)
- JWT / OAuth2 authentication
- Pytest

## Current Features

- JWT/OAuth2 authentication
- LangGraph workflow orchestration
- Real CrewAI specialist agents (billing, technical, account, general), each
  grounded via a Postgres-backed, Redis-cached knowledge-base tool -- a
  lightweight RAG mechanism (keyword-overlap ranking, not embeddings; see
  `backend/tools/README.md`), seeded with real reference articles
  (`backend.scripts.seed`)
- OpenAI structured-output ticket classification (Redis-cached)
- Policy-based escalation engine, including a structured
  agent-reported-unresolved signal
- Real, Postgres-backed supervisor approval workflow (view/approve/edit/reject)
- Idempotent ticket creation (`POST /tickets`) -- a repeated
  `Idempotency-Key` replays the original response instead of creating a
  duplicate ticket
- `GET /customers` -- lists seeded customers so a caller can find a valid
  `customer_id` for `POST /tickets`, which 404s (not a raw database error)
  on an unknown one
- Distributed (Redis-backed) rate limiting, keyed by authenticated user or
  anonymous IP, with graceful in-memory fallback if Redis is unavailable
- Best-effort LangGraph workflow checkpoints (Redis) for diagnostics/recovery
- Audit logging (real Postgres `audit_logs` rows)
- PostgreSQL persistence layer (repository pattern), with a real Alembic
  migration for every table (`alembic upgrade head`; `alembic check`/
  `tests/integration/test_schema_migrations.py` guard against the models
  and the live schema drifting apart again)
- Dockerized development environment (API, Postgres, Redis, Adminer, RedisInsight)
- Pytest test suite (167 tests: 159 unit tests with Redis/Postgres mocked,
  plus 8 `tests/integration/` tests against a real Redis and/or Postgres
  that skip themselves if the service isn't reachable)

## Authentication

SupportOps AI secures API endpoints using OAuth2 Password Flow with JWT 
authentication. Passwords are hashed with bcrypt, authenticated users are resolved
 through FastAPI dependencies, and the flow can be exercised through Swagger UI.

## Workflow Orchestration

The LangGraph workflow backbone (`backend/graph/`) compiles a fixed graph —
`load_ticket → classify_ticket → select_agent → execute_agent →
confidence_evaluation → persist_results` — and the topology has stayed fixed
even as every node's implementation went from placeholder to real:
`classify_ticket` calls OpenAI (structured outputs, Redis-cached);
`execute_agent` runs a real CrewAI specialist grounded by a Postgres
knowledge-base tool (also Redis-cached); `confidence_evaluation` delegates
to the policy engine; `persist_results` enqueues a real supervisor review
row when required. Four of these nodes also save a best-effort Redis
checkpoint after they run (diagnostics/recovery, never required for
correctness -- see "Redis: Ephemeral Infrastructure" below).

`POST /tickets` (`backend/api/routes/tickets.py`) is the first real HTTP
entry point into this graph, and is idempotent: a repeated
`Idempotency-Key` header replays the original response instead of creating
a duplicate ticket and re-running the workflow. `customer_id` is validated
against Postgres before the insert, so an unknown one returns a clean `404`
(`backend.services.ticket.CustomerNotFound`) instead of a raw foreign-key
violation; `GET /customers` (`backend/api/routes/customers.py`) lists valid
`customer_id` values to use.

![Compiled Workflow Graph](docs/screenshots/02-workflow.png)

## Supervisor Approval Queue

`confidence_evaluation_node` delegates human-review decisions to
`backend/policy/rules.py::evaluate_policy` -- deterministic keyword/threshold
rules (refund, legal, lawsuit, attorney, security, breach, fraud,
low-confidence) plus a structured `agent_unresolved` signal the CrewAI agent
itself reports (never decides). Flagged tickets are enqueued as a real
`ApprovalRequest` row (Postgres) via `backend/api/supervisor.py`, protected
by Supervisor/Admin JWT roles:

- `GET /supervisor/queue` — list tickets pending approval
- `GET /supervisor/queue/{ticket_id}` — fetch a single queue entry
- `POST /supervisor/queue/{ticket_id}/approve` — approve a ticket's draft response
- `POST /supervisor/queue/{ticket_id}/edit` — modify the draft before approving
- `POST /supervisor/queue/{ticket_id}/reject` — reject a ticket's draft response

Every view/approve/edit/reject action writes a real `audit_logs` row
(`backend/services/audit.py`).

## Redis: Ephemeral Infrastructure

PostgreSQL is the system of record for all business data -- tickets,
approval requests, audit logs, users. Redis is ephemeral infrastructure: it
only ever holds data that can safely expire or be rebuilt, and a Redis
outage never puts PostgreSQL data at risk. Four features are built on it,
each through a small purpose-built class rather than raw Redis calls
scattered through the codebase (`backend/core/redis_client.py`'s shared
client is injected everywhere):

| Feature | Solves | Backing class |
| --- | --- | --- |
| Distributed rate limiting | A single in-memory limiter doesn't share counters across multiple API instances | `backend/core/rate_limit.py` |
| Idempotency | A retried `POST /tickets` must never create a second ticket | `backend.services.idempotency.IdempotencyStore` |
| Workflow checkpoints | A crash mid-workflow left no record of the last completed stage | `backend.graph.checkpoint.WorkflowCheckpointStore` |
| AI classification + knowledge-base caches | Identical ticket text or KB lookups shouldn't re-hit OpenAI/Postgres every time | `backend.core.cache.RedisCache` |

**Two degradation policies, chosen per feature, not uniformly:** caching and
checkpoints fail *open* (a miss just recomputes; nothing is ever blocked or
corrupted). Rate limiting fails open too, but to a *different*, looser
blanket ceiling (`in_memory_fallback`) rather than each route's own
configured limit. Idempotency is the one exception: it fails *closed* --
`POST /tickets` returns `503` if Redis can't be reached to check an
`Idempotency-Key`, because silently proceeding could let a genuine duplicate
through, and "duplicate ticket creation must never occur" is a correctness
requirement, not a performance nicety.

This separation is what lets the platform honestly claim: *PostgreSQL is the
system of record for all business data, while Redis provides high-performance
ephemeral infrastructure — and if Redis is unavailable, no permanent
business data is lost.* See `docs/architecture.md`'s "Redis: Ephemeral
Infrastructure" section for the full write-up.

**Loop-scoped clients/engines, not one process-wide singleton:** both
`redis.asyncio.Redis` and SQLAlchemy's async (asyncpg) engine hold
connections bound to whichever event loop first uses them and must never be
reused from a different one. This app legitimately runs two long-lived loops
-- FastAPI's own request-handling loop, and one dedicated background loop
`backend.core.asyncio_utils.run_sync` uses to bridge LangGraph's synchronous
node functions (running inside `asyncio.to_thread`) back into async
Redis/Postgres calls -- so `get_redis_client()` (`backend/core/redis_client.py`)
and `async_session_factory()` (`backend/database/session.py`) each hand out
one client/engine per calling loop rather than one for the whole process.
Sharing one across both loops used to crash with a `RuntimeError` -- for
Postgres specifically, it poisoned a pooled connection so a *later,
unrelated* request drawing that same connection would 500, regardless of
what it was doing (this is why it could look like only requests with an
`Idempotency-Key` were affected, when the real trigger was just which pooled
connection a request happened to draw). See the module docstrings, and
`tests/integration/test_ticket_workflow.py` /
`tests/integration/test_idempotency_cross_loop.py` for real-Redis/real-Postgres
regression tests of both.

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
│   └── versions/
│       ├── 8f0d1bb0d4bb_initial_schema_baseline.py                 # reconstructed baseline, see its docstring
│       ├── 757988297d96_add_knowledge_articles_and_approval_.py    # knowledge_articles + approval_requests AI-context columns
│       └── 26f06c6b17b3_make_approval_requests_decided_at_.py      # decided_at -> TIMESTAMPTZ
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
│   │   ├── supervisor.py          # GET/POST /supervisor/queue/... — real, Postgres-backed approval queue
│   │   │
│   │   ├── routes/               # APIRouter modules
│   │   │   ├── health.py
│   │   │   ├── tickets.py         # POST /tickets — idempotent ticket creation + LangGraph workflow
│   │   │   └── customers.py       # GET /customers — discover a valid customer_id for POST /tickets
│   │   │
│   │   ├── dependencies/         # FastAPI Depends providers (auth, db session, ...)
│   │   │
│   │   └── middleware/           # ASGI middleware (logging, correlation IDs, ...)
│   │
│   ├── agents/                   # CrewAI domain specialists -- no manager agent
│   │   ├── README.md
│   │   ├── base.py                # SpecialistAgent -- shared CrewAI Agent/Task/Crew/error-handling base
│   │   │
│   │   ├── billing/agent.py       # Billing specialist
│   │   ├── technical/agent.py     # Technical specialist
│   │   ├── account/agent.py       # Account specialist
│   │   └── general/agent.py       # General/fallback specialist
│   │
│   ├── graph/                     # LangGraph workflow orchestration backbone
│   │   ├── README.md
│   │   ├── state.py               # WorkflowState + TicketCategory/SupportAgentType/WorkflowStatus enums
│   │   ├── classifier.py          # classify_ticket() -- OpenAI structured-output classification (Redis-cached)
│   │   ├── checkpoint.py          # WorkflowCheckpointStore -- best-effort Redis execution checkpoints
│   │   ├── nodes.py                # load_ticket, classify_ticket, select_agent, execute_agent, confidence_evaluation, persist_results
│   │   └── workflow.py             # build_workflow() / get_graph() — compiles the node graph
│   │
│   ├── policy/                   # Routing, escalation, and guardrail business rules
│   │   ├── README.md
│   │   └── rules.py               # evaluate_policy() — keyword/threshold + agent_unresolved escalation
│   │
│   ├── auth/                     # JWT/OAuth2 authentication & authorization
│   │   ├── README.md
│   │   ├── hashing.py             # Password hashing/verification (passlib/bcrypt)
│   │   ├── jwt.py                 # Access-token issuance & verification (python-jose)
│   │   ├── dependencies.py        # get_current_user, get_current_active_user, require_role
│   │   ├── rate_limit_key.py      # resolve_rate_limit_key() -- user-or-IP rate-limit key resolution
│   │   └── router.py              # POST /auth/login, GET /auth/me
│   │
│   ├── core/                     # Framework-level infra shared across the API
│   │   ├── README.md
│   │   ├── logging.py             # configure_logging(), get_logger() -- shared app logging
│   │   ├── rate_limit.py          # limiter -- Redis-backed slowapi rate limiting, in-memory fallback
│   │   ├── security.py            # OAuth2PasswordBearer scheme, 401/403 exceptions
│   │   ├── redis_client.py        # get_redis_client() -- the one shared redis.asyncio client
│   │   ├── cache.py               # RedisCache -- generic cache used by the classifier + knowledge-base tool
│   │   └── asyncio_utils.py       # run_sync() -- sync/async bridge for CrewAI tools + LangGraph nodes
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
│   │   │   ├── approval_request.py    # extended: draft_response, retrieved_context, selected_agent, matched_policy_rules
│   │   │   ├── audit_log.py
│   │   │   └── knowledge_article.py
│   │   │
│   │   ├── migrations/            # Alembic migration environment
│   │   │   └── README.md
│   │   │
│   │   └── repositories/          # Repository-pattern data access
│   │       ├── knowledge_article.py
│   │       ├── approval_request.py
│   │       ├── audit_log.py
│   │       ├── ticket.py
│   │       └── customer.py        # read-only: get_by_id (used by services/ticket.py), list_all (GET /customers)
│   │
│   ├── services/                 # Application services (routes depend on these)
│   │   ├── README.md
│   │   ├── audit.py               # log_audit_event() — real AuditLog persistence, best-effort
│   │   ├── idempotency.py         # IdempotencyStore -- atomic Redis claim, fails closed
│   │   └── ticket.py              # create_ticket() -- idempotency + persistence + the LangGraph workflow
│   │
│   ├── tools/                    # Tool implementations exposed to agents
│   │   ├── README.md
│   │   └── knowledge_base.py      # KnowledgeBaseSearchTool -- Postgres search, Redis-cached
│   │
│   ├── schemas/                  # Pydantic request/response & internal contracts
│   │   ├── README.md
│   │   ├── auth.py                # Token, AuthenticatedUser
│   │   ├── supervisor.py          # SupervisorQueueItem/Response, ApprovalDecisionRequest, EditDraftRequest
│   │   ├── ticket.py              # TicketCreateRequest/Response
│   │   └── customer.py            # CustomerResponse/CustomerListResponse (GET /customers)
│   │
│   ├── config/                   # Settings (env-driven configuration)
│   │   ├── README.md
│   │   └── settings.py
│   │
│   └── scripts/                  # One-off scripts (python -m backend.scripts.<name>)
│       ├── README.md
│       ├── seed.py                # Idempotent dev-data seed (users, customers, tickets, knowledge articles)
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
│   ├── unit/                     # Fast, isolated tests (mirrors backend/); Redis mocked via fakeredis
│   │   ├── README.md
│   │   ├── test_main.py
│   │   ├── agents/
│   │   │   └── test_base_agent.py
│   │   │
│   │   ├── api/
│   │   │   ├── conftest.py        # shared JWT/session/ApprovalRequest test doubles
│   │   │   ├── test_supervisor.py
│   │   │   ├── test_supervisor_adversarial.py
│   │   │   ├── test_tickets.py
│   │   │   └── test_customers.py
│   │   │
│   │   ├── auth/
│   │   │   ├── test_jwt.py
│   │   │   └── test_rate_limit_key.py
│   │   │
│   │   ├── core/
│   │   │   ├── test_logging.py
│   │   │   ├── test_rate_limit.py
│   │   │   ├── test_cache.py
│   │   │   ├── test_asyncio_utils.py
│   │   │   └── test_redis_client.py
│   │   │
│   │   ├── database/repositories/
│   │   │   ├── test_knowledge_article.py
│   │   │   └── test_customer.py
│   │   │
│   │   ├── graph/
│   │   │   ├── test_nodes.py
│   │   │   ├── test_classifier.py
│   │   │   ├── test_checkpoint.py
│   │   │   ├── test_execute_agent_node.py
│   │   │   └── test_persist_results_node.py
│   │   │
│   │   ├── policy/
│   │   │   ├── test_rules.py
│   │   │   └── test_adversarial_inputs.py
│   │   │
│   │   ├── services/
│   │   │   ├── test_audit.py
│   │   │   ├── test_idempotency.py
│   │   │   ├── test_ticket.py
│   │   │   └── test_ticket_execute.py
│   │   │
│   │   └── tools/
│   │       └── test_knowledge_base.py
│   │
│   ├── integration/              # Tests against real Redis and/or real Postgres, see README
│   │   ├── README.md
│   │   ├── conftest.py            # real_redis, real_postgres, real_customer (skip if unreachable), client, issue_token
│   │   ├── test_ticket_workflow.py         # real POST /tickets against real Redis -- see backend/core/asyncio_utils.py
│   │   ├── test_idempotency_cross_loop.py  # real POST /tickets against real Redis + Postgres -- see backend/database/session.py
│   │   └── test_schema_migrations.py       # models vs. live schema, via alembic's own diff engine
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

# Check for model changes with no matching migration yet (run this after
# changing anything in backend/database/models/, before committing)
alembic check

# Seed baseline dev data: 4 users, 5 demo customers, 15 demo tickets, and 11
# knowledge-base articles for KnowledgeBaseSearchTool to retrieve.
# Idempotent -- safe to run more than once.
python -m backend.scripts.seed
```

### Running the LangGraph workflow

```bash
# Runs the compiled workflow against a sample ticket and prints the final
# state. Requires a real OPENAI_API_KEY (classification + the CrewAI
# specialist both call OpenAI); Postgres/Redis are optional -- the
# knowledge-base lookup, workflow checkpoints, and supervisor-queue write
# all degrade gracefully without them (see backend/graph/README.md).
python -m backend.scripts.run_workflow
```

### Running tests

```bash
pytest

# tests/integration/ exercises a real Redis/Postgres (docker compose up -d
# redis postgres) -- each test skips itself if the service it needs isn't
# reachable, so a plain `pytest` above is always safe to run either way.
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
