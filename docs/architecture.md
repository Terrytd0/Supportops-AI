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
- Redis – Caching and short-lived workflow state
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
                               +----------------------+
                               |      FastAPI API     |
                               +----------+-----------+
                                          |
                                          v
                               +----------------------+
                               |      LangGraph       |
                               | Workflow Orchestrator|
                               +----------+-----------+
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
                         +------------------+        +------------------+
                         | PostgreSQL       |        | Redis            |
                         | Audit & Tickets  |        | Cache & State    |
                         +------------------+        +------------------+

The architecture separates request handling, workflow orchestration, AI reasoning, and persistent storage into distinct layers. LangGraph coordinates workflow execution while CrewAI provides domain-specific reasoning. Business policies determine whether responses are delivered automatically or escalated to human support.
             
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
| PostgreSQL      | Stores tickets, audit logs, users, and workflow history      |
| Redis           | Caches temporary workflow state and frequently accessed data |

Each component has a clearly defined responsibility, promoting separation of concerns and allowing individual parts of the system to evolve independently as the platform grows.

## Request Lifecycle

       Customer Request
              │
              ▼
    FastAPI receives request
              │
              ▼
     Create Support Ticket
              │
              ▼
   LangGraph starts workflow
              │
              ▼
       Classify Ticket
              │
              ▼
    Select Specialist Agent
              │
              ▼
      Generate AI Response
              │
              ▼
     Confidence Evaluation
       ┌──────┴────────┐
       │               │
       ▼               ▼
    Auto Send   Human Review
       │               │
       └───────┬───────┘
               ▼
          Audit Log
               ▼
         Ticket Closed

The request lifecycle illustrates the end-to-end processing of a customer support request. Incoming requests are received through the FastAPI service, converted into support tickets, and processed by a LangGraph workflow. After the appropriate specialist AI agent generates a response, the workflow performs a confidence and policy evaluation to determine whether the response can be sent automatically or requires human review. All outcomes are recorded for auditing before the ticket is closed.

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

### Billing Agent

Responsible for:
- invoices
- subscriptions
- refunds
- billing disputes

### Technical Agent

Responsible for:
- bugs
- troubleshooting
- outages
- diagnostics

### Account Agent

Responsible for:
- password resets
- profile updates
- account verification

### General Agent

Responsible for:
- general product questions
- FAQs
- company policies
- routing non-specialized requests

CrewAI coordinates specialist AI agents responsible for domain-specific reasoning. Human escalation is not performed by CrewAI; instead, LangGraph routes tickets requiring manual intervention to human support staff according to business policies.

## Data Architecture

                +----------------------+
                |     FastAPI API      |
                +----------+-----------+
                           |
                           v
                    +-------------+
                    | LangGraph   |
                    +------+------+ 
                           |
             +-------------+-------------+
             |                           |
             v                           v
      +---------------+          +---------------+
      | PostgreSQL    |          | Redis         |
      | Persistent    |          | Temporary     |
      | Data          |          | Workflow State|
      +---------------+          +---------------+

SupportOps AI separates persistent business data from temporary runtime state. PostgreSQL stores durable application data such as tickets, users, audit logs, and workflow history, while Redis stores short-lived workflow state and cached information used during request processing.

| **Data Store** | **Purpose**                              |
| ---------- | -------------------------------------------- |
| PostgreSQL | Tickets, users, audit logs, workflow history |
| Redis      | Workflow state, cache, session data          |


## Authentication & Authorization

SupportOps AI secures access through authentication and role-based authorization. Authentication verifies the identity of users accessing the platform, while authorization determines which actions each user is permitted to perform.

| **Role**      | **Permissions**                                         |
| ------------- | ------------------------------------------------------- |
| Customer      | Submit and view support tickets                         |
| Support Agent | View and update assigned tickets                        |
| Administrator | Manage users, workflows, and system configuration       |
| AI Services   | Execute workflow tasks through controlled internal APIs |

- API authentication
- Role-Based Access Control (RBAC)
- Least-privilege access
- Audit logging for privileged actions

## Caching Strategy

Redis improves system performance by reducing repeated database queries and storing temporary workflow state during request execution.

| **Cached Data**                 | **Purpose**                |
| ------------------------------- | -------------------------- |
| Workflow State                  | Resume LangGraph execution |
| Frequently Accessed Ticket Data | Reduce database reads      |
| Session Information             | Faster request handling    |

Cached information is considered temporary and can be reconstructed from persistent storage when necessary.

## Deployment Architecture

                  Internet
                      │
                      ▼
             +----------------+
             | FastAPI Service|
             +--------+-------+
                      │
                      ▼
             +----------------+
             |   LangGraph    |
             | Workflow Engine|
             +---+--------+---+
                 │        │
                 │        ▼
                 │  +----------------------+
                 │  |        CrewAI        |
                 │  | Specialist AI Agents |
                 │  +----------------------+
                 │
        +--------+--------+
        │                 │
        ▼                 ▼
   PostgreSQL          Redis

The platform is containerized using Docker. FastAPI serves as the application entry point, LangGraph orchestrates workflows, CrewAI executes specialist AI agents that perform domain-specific reasoning, PostgreSQL stores persistent data, and Redis provides temporary workflow storage and caching.

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
| Cache     | Hit ratio, memory usage                 |

- Request logs
- Workflow execution logs
- Agent decision logs
- Error logs
- Audit logs

These metrics support troubleshooting, performance optimization, and operational monitoring while maintaining an auditable record of AI-assisted decisions.

