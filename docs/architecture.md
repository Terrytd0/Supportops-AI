# Architecture

## Status

Version 1.0 – Initial Solution Architecture

This document defines the high-level architecture of SupportOps AI and describes the major system components, data flow, technology stack, and deployment model used during Sprint 4.

## About This Project

SupportOps AI is a fictional case study created for portfolio and educational purposes. This document presents the proposed solution architecture for the platform and demonstrates enterprise software architecture and AI system design practices.

## Purpose

This document describes the high-level system architecture of SupportOps AI:
component boundaries, data flow, and the runtime topology of the multi-agent
support platform.

## Technology Stack

The SupportOps AI platform is built using the following core technologies.

- FastAPI – Backend API framework
- LangGraph – Workflow orchestration
- CrewAI – Specialist AI agent framework
- PostgreSQL – Persistent application and audit data
- Redis – Ephemeral infrastructure: distributed rate limiting, idempotency, workflow checkpoints, AI/knowledge caches
- Docker – Development and deployment containerization

## Design Principles

The architecture of SupportOps AI is guided by the following principles:

- Modular component design
- Separation of concerns
- Human-in-the-loop for high-risk decisions
- Auditability and traceability
- Scalability through workflow orchestration
- Security by design

## High-Level System Architecture (diagram)

                              +-----------------------+
                              |   Customer Channels   |
                              | Email • Chat • Portal |
                              +-----------+-----------+
                                          |
                                          v
                               +----------------------+          +-------------------+
                               |      FastAPI API     |<-------->| Redis: rate limits,|
                               +----------+-----------+          | idempotency keys   |
                                          |                      +-------------------+
                                          v
                               +----------------------+          +-------------------+
                               |      LangGraph       |<-------->| Redis: workflow    |
                               | Workflow Orchestrator|          | checkpoints        |
                               +----------+-----------+          +-------------------+
                                          |
               +-----------------+------------------+----------------+
               |                 |                  |                |
               v                 v                  v                v
       +---------------+  +---------------+  +---------------+ +---------------+
       | Billing Agent |  | General Agent |  |Technical Agent| | Account Agent |
       |   (CrewAI)    |  |   (CrewAI)    |  |   (CrewAI)    | |   (CrewAI)    |
       +-------+-------+  +-------+-------+  +-------+-------+ +-------+-------+
             \             \                |                /            /
              \             \               |               /            /
               +------------------+-------------------+-----------------+
                                            |
                                            v
                                 +----------------------+
                                 | Policy Evaluation    |
                                 | Confidence Evaluation|
                                 +-----+-----------+----+
                                       |           |
                             Auto Reply|           |Human Review
                                       |           |
                                       v           v
                              +--------------+  +------------------+
                              | Customer     |  | Human Support    |
                              +------+-------+  +---------+--------+
                                     |                    |
                                     +---------+----------+
                                               |
                                 +-------------+-------------+
                                  |                           |
                                  v                           v
                         +------------------+        +-------------------------+
                         | PostgreSQL       |        | Redis                   |
                         | Tickets, Approval|        | Rate limits, idempotency|
                         | Requests, Audit  |        | keys, checkpoints,      |
                         | Logs, Users      |        | AI/knowledge caches     |
                         +------------------+        +-------------------------+

The architecture separates request handling, workflow orchestration, AI reasoning, and persistent storage into distinct layers. LangGraph coordinates workflow execution while CrewAI provides domain-specific reasoning. Business policies determine whether responses are delivered automatically or escalated to human support. Redis touches the request path in four places (rate limiting and idempotency at the API layer, checkpoints and AI/knowledge caches during workflow execution) but never holds anything PostgreSQL doesn't already have or couldn't recompute -- see "Redis: Ephemeral Infrastructure" below.
             
## Component Responsibilities

| **Component**   | **Responsibility**                                           |
| --------------- | ------------------------------------------------------------ |
| FastAPI         | Exposes REST endpoints and validates incoming requests       |
| LangGraph       | Controls workflow execution and state transitions            |
| CrewAI          | Coordinates specialist AI agents during workflow execution.  |
| Billing Agent   | Handles billing-related requests                             |
| Technical Agent | Handles troubleshooting and technical support                |
| Account Agent   | Handles account management tasks                             |
| General Agent   | Handles general inquiries                                    |
| Human Support   | Reviews escalated or high-risk requests                      |
| PostgreSQL      | System of record: tickets, approval requests, audit logs, users |
| Redis           | Ephemeral infra: distributed rate limiting, idempotency keys, workflow checkpoints, AI/knowledge caches |

Each component has a clearly defined responsibility, promoting separation of concerns and allowing individual parts of the system to evolve independently as the platform grows.

## Request Lifecycle

       Customer Request (POST /tickets, Idempotency-Key)
              │
              ▼
    FastAPI receives request
              │
              ▼
   Idempotency check (Redis) ──── key seen before? ──► Return original response
              │ no
              ▼
     Create Support Ticket (PostgreSQL)
              │
              ▼
   LangGraph starts workflow
              │
              ▼
       Classify Ticket (OpenAI, Redis-cached)
              │
              ▼
    Select Specialist Agent
              │
              ▼
      Generate AI Response (CrewAI, knowledge-base Redis-cached)
              │
              ▼
     Confidence Evaluation (Policy Engine)
       ┌──────┴────────┐
       │               │
       ▼               ▼
    Auto Send   Human Review (Supervisor Queue)
       │               │
       └───────┬───────┘
               ▼
          Audit Log (PostgreSQL)
               ▼
         Ticket Closed

The request lifecycle illustrates the end-to-end processing of a customer support request. Incoming requests are received through the FastAPI service; an `Idempotency-Key` is checked against Redis first so a retried request replays the original response instead of creating a duplicate ticket. A new request is converted into a support ticket (PostgreSQL) and processed by a LangGraph workflow. After the appropriate specialist AI agent generates a response, the workflow performs a confidence and policy evaluation to determine whether the response can be sent automatically or requires human review via the supervisor queue. All outcomes are recorded for auditing before the ticket is closed.

## LangGraph Workflow

            Start
              │
              ▼
          Load Ticket
              │
              ▼
        Classify Ticket
              │
              ▼
         Select Agent
              │
              ▼
         Execute Agent
              │
              ▼
     Confidence Evaluation
       ┌──────┴────────┐
       ▼               ▼
   Auto Reply    Human Approval
       │               │
       └──────┬────────┘
              ▼
        Persist Results
              ▼
             End

LangGraph orchestrates the execution of each support workflow by maintaining state and coordinating decision-making throughout the request lifecycle. It loads the support ticket, classifies the request, selects the appropriate specialist AI agent, evaluates the generated response against business policies and confidence thresholds, and persists the final workflow state. This centralized orchestration enables reliable, auditable, and extensible workflow execution.

Node names above map directly to `backend/graph/nodes.py`: `load_ticket_node`, `classify_ticket_node`, `select_agent_node`, `execute_agent_node`, `confidence_evaluation_node`, `persist_results_node`. "Auto Reply" and "Human Approval" aren't separate nodes -- both paths converge into `persist_results_node`, which enqueues a real supervisor-queue row only when `requires_human_review` is set. Four nodes (classification, agent selection, specialist execution, policy evaluation) also save a best-effort Redis checkpoint after they run; see "Redis: Ephemeral Infrastructure" below.

## CrewAI Agent Architecture

                           CrewAI
                             │
      ┌──────────────┬───────┼──────┬──────────────┐
      ▼              ▼              ▼              ▼
 Billing Agent  General Agent  Technical Agent  Account Agent
      │              │              │              │
      └──────────────┴───────┼──────┴──────────────┘
                             ▼
                    Generated Response

Each agent grounds its response with a lightweight RAG (retrieval-augmented
generation) step before generating: `KnowledgeBaseSearchTool` retrieves the
top-ranked `knowledge_articles` rows for the agent's category and feeds them
into the prompt as context, rather than relying on the LLM's own
unverifiable training knowledge. "Lightweight" specifically means the
ranking is keyword overlap between the query and article text
(`KnowledgeArticleRepository.search`), not vector/embedding similarity --
appropriate for the current, small (~10-articles-per-category), Postgres-backed
knowledge base; see `backend/tools/README.md`.

### Billing Agent

Responsible for:
- invoices
- refunds
- payments
- subscriptions
- pricing
- billing disputes

### Technical Agent

Responsible for:
- login problems
- bugs
- crashes
- API issues
- troubleshooting / other product issues

### Account Agent

Responsible for:
- account settings
- profile information
- permissions
- access issues / user management

### General Agent

Responsible for:
- greetings
- FAQs
- anything that doesn't clearly belong to billing, technical, or account
  (fallback only -- it does **not** route or triage; see below)

CrewAI coordinates specialist AI agents responsible for domain-specific reasoning. There is no manager/router agent: `backend.graph.nodes.select_agent_node` (LangGraph) decides which specialist handles a ticket, based on `backend.graph.classifier.classify_ticket`'s OpenAI classification -- agents never route to each other or decide escalation themselves (see `backend/agents/README.md`). Human escalation is not performed by CrewAI; instead, LangGraph routes tickets requiring manual intervention to human support staff according to business policies.

## Data Architecture

    +----------------------+
    |     FastAPI API      |----+
    +----------+-----------+    |
               |                |
               v                |
        +-------------+         |    +----------------------------+
        | LangGraph   |---------+--->| Redis                      |
        +------+------+              | (all ephemeral -- rate      |
               |                     | limits, idempotency keys,   |
               v                     | checkpoints, AI/knowledge   |
        +---------------+            | caches -- see table below) |
        | PostgreSQL    |            +----------------------------+
        | Persistent    |
        | Data          |
        +---------------+

SupportOps AI separates persistent business data from temporary runtime state. PostgreSQL is the **system of record**: tickets, approval requests, audit logs, and users all live there, and nothing about them is ever only in Redis. Redis is **ephemeral infrastructure**: every key it holds either expires on its own or can be safely rebuilt (a cache miss just re-runs the computation; a missing checkpoint just means less diagnostic history; an idempotency key past its TTL just means the next duplicate isn't caught). If Redis is unavailable, PostgreSQL data is never at risk -- see "Redis: Ephemeral Infrastructure" below for how each feature degrades.

| **Data Store** | **Purpose**                              |
| ---------- | -------------------------------------------- |
| PostgreSQL | Tickets, approval requests, audit logs, users -- permanent business data |
| Redis      | Rate-limit counters, idempotency keys, workflow checkpoints, AI/knowledge caches -- all ephemeral |


## Authentication & Authorization

SupportOps AI secures access through JWT/OAuth2 authentication and role-based authorization (`backend/auth/`). Authentication verifies the identity of users accessing the platform (`POST /auth/login`), while `require_role(...)` dependencies determine which actions each authenticated user is permitted to perform. The three roles below (`backend.database.enums.UserRole`) are platform staff -- customers are a separate, unauthenticated business entity (`customers` table) tickets are submitted *for*, not JWT principals themselves; see `docs/database_schema.md`'s "User Roles".

| **Role**   | **Permissions**                                                     |
| ---------- | --------------------------------------------------------------------- |
| Agent      | Create tickets (`POST /tickets`), view assigned tickets, generate AI drafts |
| Supervisor | Everything an Agent can, plus the full supervisor queue: view/approve/edit/reject AI drafts (`/supervisor/queue/...`) |
| Admin      | Everything a Supervisor can, plus user management and system configuration (not yet implemented as its own endpoints) |

`POST /tickets` only requires *any* authenticated, active user (no specific role); `/supervisor/queue/...` requires Supervisor or Admin (`require_role(UserRole.SUPERVISOR, UserRole.ADMIN)`).

- API authentication (JWT bearer tokens, OAuth2 password flow)
- Role-Based Access Control (RBAC) via `require_role`
- Least-privilege access
- Audit logging for privileged actions (every supervisor view/approve/edit/reject writes a real `audit_logs` row)

## Redis: Ephemeral Infrastructure

> PostgreSQL is the system of record for all business data, while Redis provides high-performance ephemeral infrastructure. Redis powers distributed rate limiting, idempotency, LangGraph checkpointing, and caching of expensive AI operations. If Redis is unavailable, no permanent business data is lost because PostgreSQL remains the authoritative data store.

Redis was introduced to solve four concrete production problems the platform otherwise couldn't -- not "because Redis is a common tool to have." Each is implemented behind a small, purpose-built class (`backend/core/redis_client.py`'s shared client, injected everywhere else), never raw Redis calls scattered through route/node code:

| **Capability**              | **Problem it solves**                                                             | **Backing class**                                    |
| ---------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Distributed rate limiting     | slowapi's default in-memory limiter doesn't share counters across multiple API instances -- each process would enforce its own limit | `backend/core/rate_limit.py` (Redis-backed `slowapi.Limiter`) |
| Idempotency                   | A client retrying `POST /tickets` after a timeout must never create a second ticket | `backend.services.idempotency.IdempotencyStore`       |
| LangGraph checkpoints         | A crash mid-workflow left no record of which stage a ticket's run last reached      | `backend.graph.checkpoint.WorkflowCheckpointStore`    |
| AI classification cache       | Identical ticket text re-running an OpenAI classification call is pure waste        | `backend.graph.classifier` (via `backend.core.cache.RedisCache`) |
| Knowledge-retrieval cache      | Identical (category, query) knowledge-base lookups re-hitting Postgres repeatedly    | `backend.tools.knowledge_base` (via `RedisCache`)     |

### Two degradation policies, chosen deliberately per feature

Not every Redis-backed feature should behave the same way when Redis is unavailable -- the right answer depends on whether Redis is on the read path of a *correctness* guarantee or purely a *performance* optimization:

- **Fail open (degrade silently, keep serving traffic):** the AI classification cache, the knowledge-retrieval cache, and workflow checkpoints. A cache miss just means recomputing the answer; a missing checkpoint just means less diagnostic history. None of these ever block or corrupt a request. Rate limiting also fails open, but to a *different* mechanism -- slowapi's `in_memory_fallback`, a single blanket per-process ceiling that applies while Redis is down, looser than (and not a re-application of) each route's own configured limit.
- **Fail closed (reject rather than risk a mistake):** idempotency. "Duplicate ticket creation must never occur" is a correctness requirement, not a nicety -- if Redis can't be reached to check an `Idempotency-Key`, `POST /tickets` returns `503` rather than silently risking a duplicate. The client's own retry (the whole reason idempotency keys exist) is what recovers once Redis is back.

In every case, the failure mode is a Redis-side problem contained to Redis-side functionality. Tickets, approval requests, and audit logs are written directly to PostgreSQL and are never at risk from a Redis outage.

### Client/engine lifetime: loop-scoped, not process-wide

Both `redis.asyncio.Redis` and SQLAlchemy's async engine (asyncpg) hold connections (and the asyncio primitives they use internally) bound to whichever event loop first uses them, and neither must ever be reused from a different one. This app legitimately runs two long-lived event loops for its whole life, not one:

1. **FastAPI's own request-handling loop** -- used directly, via a plain `await`, by anything that's already async: `IdempotencyStore` and `_execute`'s customer/ticket writes (`backend.services.ticket`), rate limiting (`backend.core.rate_limit`), `get_current_user`'s DB lookup (`backend.auth.dependencies`).
2. **`backend.core.asyncio_utils.run_sync`'s dedicated background loop** -- LangGraph's node functions are synchronous by contract, and `POST /tickets` runs the whole compiled graph via `asyncio.to_thread(get_graph().invoke, ...)` (`backend.services.ticket._execute`) so it doesn't block the request-handling loop. Every node that needs Redis (the classification cache, workflow checkpoints) or Postgres (`_enqueue_supervisor_review`'s write, the knowledge-base tool's search) calls `run_sync`, which bridges back into async code -- always on this one loop, never a fresh one per call.

Both `get_redis_client()` (`backend/core/redis_client.py`) and `async_session_factory()` (`backend/database/session.py`) hand out one client/engine per *calling* loop rather than a single process-wide singleton, precisely because of the above. Sharing one across both loops is what used to raise `RuntimeError: Future attached to a different loop` (Redis; or, on Windows' Proactor loop, `RuntimeError: Event loop is closed`) or, for Postgres specifically, poisoned a pooled connection so that `pool_pre_ping`'s per-checkout health check raised the same class of `RuntimeError` for *every later request* that happened to be handed that connection -- regardless of what that request was doing, which is why it could look like it only affected one code path (e.g. requests carrying an `Idempotency-Key`) when it was really about which pooled connection a request's turn happened to draw. `tests/integration/test_ticket_workflow.py` and `tests/integration/test_idempotency_cross_loop.py` are real-Redis/real-Postgres regression tests of these two cases.

## Deployment Architecture

                  Internet
                      │
                      ▼
             +----------------+
             | FastAPI Service|<─────► Redis (rate limits, idempotency)
             +--------+-------+
                      │
                      ▼
             +----------------+
             |   LangGraph    |<─────► Redis (checkpoints)
             | Workflow Engine|
             +---+--------+---+
                 │        │
                 │        ▼
                 │  +----------------------+
                 │  |        CrewAI        |<─────► Redis (AI/knowledge caches)
                 │  | Specialist AI Agents |
                 │  +----------------------+
                 │
        +--------+--------+
        │                 │
        ▼                 ▼
   PostgreSQL          Redis
  (system of record)  (ephemeral, all uses above)

The platform is containerized using Docker. FastAPI serves as the application entry point, LangGraph orchestrates workflows, CrewAI executes specialist AI agents that perform domain-specific reasoning, PostgreSQL is the system of record, and Redis provides ephemeral infrastructure (rate limiting, idempotency, checkpoints, AI/knowledge caches -- see "Redis: Ephemeral Infrastructure" above). `docker-compose.yml` runs `api`, `postgres`, and `redis` as required services, plus `adminer` (Postgres) and `redisinsight` (Redis) for local inspection during development/demos.

- Docker
- Modular services
- Independent scaling
- Future cloud deployment

## Observability

Observability provides visibility into system health, workflow execution, and AI decision making.

| **Area**  | **Example Metrics**                     |
| --------- | --------------------------------------- |
| API       | Request latency, error rate             |
| LangGraph | Workflow duration, node failures        |
| CrewAI    | Agent execution time, confidence scores |
| Database  | Query latency                           |
| Redis     | Cache hit ratio, rate-limit throttle rate, fallback-to-in-memory events, idempotency conflicts |

- Request logs
- Workflow execution logs
- Agent decision logs
- Error logs
- Audit logs

These metrics support troubleshooting, performance optimization, and operational monitoring while maintaining an auditable record of AI-assisted decisions.

