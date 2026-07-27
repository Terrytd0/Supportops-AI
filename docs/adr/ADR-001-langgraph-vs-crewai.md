# ADR-001: LangGraph vs. CrewAI (and why we use both)

## Status

Accepted — Sprint 4

## Context

SupportOps AI needs to orchestrate multiple specialized support agents
(billing, technical, account, General) under a manager/supervisor agent, with reliable
control flow, state persistence, and human-in-the-loop escalation. Two
candidate frameworks are in the stack: **LangGraph** and **CrewAI**.

- **LangGraph** provides explicit, graph-based control flow with first-class
  state persistence/checkpointing, conditional routing, and cycles — well
  suited to modeling the deterministic parts of a support workflow (routing,
  retries, escalation, human-in-the-loop interrupts).
- **CrewAI** provides a higher-level role/task abstraction for composing
  collaborating agents (crews), which is well suited to expressing the
  domain-specific agents (billing, technical, account, General) as roles with tools and
  goals, without hand-rolling their internal reasoning loop.

## Decision

LangGraph is adopted as the primary workflow orchestration framework for SupportOps AI, while CrewAI is used to implement specialist AI agents responsible for domain-specific reasoning.

LangGraph owns the overall support workflow, including ticket state management, request classification, conditional routing, policy evaluation, human-in-the-loop escalation, and workflow persistence. Each workflow invokes the appropriate CrewAI specialist agent when AI reasoning is required.

CrewAI provides the Billing, Technical, Account, and General agents. These agents generate domain-specific responses but do not control workflow execution or escalation decisions.

Workflow state is maintained by LangGraph and persisted through PostgreSQL and Redis. CrewAI agents receive only the context required to complete their assigned task and return generated responses to LangGraph for further policy evaluation.

## Consequences

### Positive

- Clear separation between workflow orchestration and AI reasoning.
- Human-in-the-loop decisions remain deterministic and auditable.
- Specialist agents can evolve independently without changing workflow logic.
- LangGraph provides reliable state management, checkpointing, and conditional routing.
- CrewAI simplifies implementation of role-based specialist agents.

### Negative

- Two frameworks increase deployment and operational complexity.
- Testing requires validation of both workflow execution and agent behaviour.
- Additional integration logic is required between LangGraph and CrewAI.
- Debugging may require tracing execution across multiple components.

## Alternatives Considered

### LangGraph Only

LangGraph could implement both workflow orchestration and specialist agent behaviour using custom nodes and prompts. While this would reduce the number of frameworks, it would require additional implementation effort to recreate role-based specialist agents and would reduce modularity.

### CrewAI Only

CrewAI could coordinate both workflow execution and specialist agents. However, SupportOps AI requires deterministic workflow control, state persistence, conditional routing, auditability, and human approval checkpoints, all of which are more naturally handled by LangGraph. Using CrewAI alone would make these workflow requirements more difficult to implement consistently.