# CLAUDE.md

Guidance for AI-assisted development (Claude Code and similar tools) in this repository.

## Project Summary

SupportOps AI is an enterprise multi-agent customer support platform. Agents
(billing, technical, account, General) are orchestrated via LangGraph and
CrewAI behind a FastAPI backend, with PostgreSQL/SQLAlchemy/Alembic for
persistence and Redis for caching and short-term agent memory.

This repository is currently a **scaffold** (Sprint 4 starting point). Most
modules contain structure and `TODO` markers only — no business logic.

## Repository Layout

- `backend/api/` — FastAPI routers, dependencies, and middleware. HTTP concerns only.
- `backend/agents/` — Domain-specific agent implementations (billing, technical, account, general).
- `backend/graph/` — LangGraph state graph definitions wiring agents together.
- `backend/policy/` — Business rules, guardrails, and routing/escalation policy.
- `backend/auth/` — JWT/OAuth2 authentication and authorization.
- `backend/database/` — SQLAlchemy models, Alembic migrations, repository pattern data access.
- `backend/services/` — Application/business services orchestrating repositories and agents.
- `backend/tools/` — Tool implementations exposed to agents (e.g. CRM lookups, ticket systems).
- `backend/schemas/` — Pydantic request/response and internal data contracts.
- `backend/config/` — Settings and environment configuration.
- `tests/` — `unit/`, `integration/`, and `fixtures/` mirroring the backend structure.
- `docs/` — Architecture, requirements, assumptions, decisions, and ADRs.

## Engineering Conventions

- **No business logic in scaffolding.** Placeholder modules should raise
  `NotImplementedError` or contain `TODO` comments, not partial implementations.
- **Layered architecture.** API routes depend on services; services depend on
  repositories and agents. Do not let routes talk to the database or agents directly.
- **Repository pattern** for all database access — no raw SQLAlchemy queries in services.
- **Schemas at boundaries.** All API input/output must be validated via Pydantic
  schemas in `backend/schemas/`; never expose ORM models directly.
- **Config via environment.** All configuration must flow through
  `backend/config/`, sourced from environment variables (12-factor). Never hardcode secrets.
- **Auth is centralized.** All authentication/authorization logic lives in
  `backend/auth/`; routes consume it via dependencies, they don't reimplement it.
- **Tests mirror source structure.** A new module under `backend/x/y.py` gets
  tests under `tests/unit/x/test_y.py` (and `tests/integration/` where relevant).
- **Migrations are generated, not hand-written**, via Alembic against the
  SQLAlchemy models in `backend/database/models/`.
- **Document decisions.** Non-obvious architectural choices belong in
  `docs/decisions.md` or a new ADR under `docs/adr/`, not just in code comments.

## Working in This Repo

- When implementing a new module, check `docs/architecture.md` and the
  relevant ADRs first for constraints already agreed upon.
- Prefer extending the existing structure over introducing new top-level
  directories; propose structural changes via an ADR.
- Keep agent, graph, and policy concerns separate: agents define *capability*,
  the graph defines *control flow*, policy defines *business rules*.
- Do not remove `TODO` markers without implementing the corresponding logic.
