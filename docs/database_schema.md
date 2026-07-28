# Database Schema

## Overview

The SupportOps AI Platform stores customer support tickets, AI agent execution history, approval workflows, audit trails, and authenticated users.

The database is designed with auditability as a primary requirement. Every significant action is recorded and linked to the user or AI agent responsible.

---

# Entity Relationship Diagram

```
Users
   │
   │ (assigned_agent_id)
   ▼
Tickets ───────────────► Customers
   │
   ├──────────────► Agent Runs
   │
   ├──────────────► Audit Logs
   │
   └──────────────► Approval Requests
```

---

# Tables

---

## users

Stores authenticated users of the platform.

### Columns

| Column | Type | Constraints |
|---------|------|-------------|
| id | UUID | PK |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| password_hash | TEXT | NOT NULL |
| full_name | VARCHAR(255) | NOT NULL |
| role | ENUM | agent, supervisor, admin |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | NOT NULL |
| updated_at | TIMESTAMP | NOT NULL |

### Relationships

- One user can be assigned many tickets.
- One user can approve many responses.
- One user can create many audit events.

---

## customers

Represents companies or individuals creating support tickets.

### Columns

| Column | Type | Constraints |
|---------|------|-------------|
| id | UUID | PK |
| name | VARCHAR(255) | NOT NULL |
| email | VARCHAR(255) | NOT NULL |
| company | VARCHAR(255) | NULL |
| tier | ENUM | standard, premium, enterprise |
| created_at | TIMESTAMP | NOT NULL |

### Relationships

- One customer can own many tickets.

---

## tickets

Primary business object.

### Columns

| Column | Type | Constraints |
|---------|------|-------------|
| id | UUID | PK |
| customer_id | UUID | FK customers.id |
| assigned_agent_id | UUID | FK users.id |
| subject | VARCHAR(255) | NOT NULL |
| description | TEXT | NOT NULL |
| priority | ENUM | low, medium, high, urgent |
| status | ENUM | new, triaged, assigned, drafted, approval_required, approved, sent, closed |
| ai_summary | TEXT | NULL |
| created_at | TIMESTAMP | NOT NULL |
| updated_at | TIMESTAMP | NOT NULL |

### Relationships

Belongs to:

- Customer
- Assigned User

Has many:

- Agent Runs
- Audit Logs
- Approval Requests

---

## agent_runs

Stores every AI workflow execution.

Every LangGraph/CrewAI execution generates one record.

### Columns

| Column | Type | Constraints |
|---------|------|-------------|
| id | UUID | PK |
| ticket_id | UUID | FK tickets.id |
| agent_name | VARCHAR(100) | NOT NULL |
| model | VARCHAR(100) | NOT NULL |
| input | JSONB | NOT NULL |
| output | JSONB | NOT NULL |
| latency_ms | INTEGER | NOT NULL |
| tokens_prompt | INTEGER | NULL |
| tokens_completion | INTEGER | NULL |
| success | BOOLEAN | NOT NULL |
| error_message | TEXT | NULL |
| created_at | TIMESTAMP | NOT NULL |

### Relationships

Belongs to:

- Ticket

---

## approval_requests

Stores supervisor approval before customer responses are sent.

### Columns

| Column | Type | Constraints |
|---------|------|-------------|
| id | UUID | PK |
| ticket_id | UUID | FK tickets.id |
| requested_by | UUID | FK users.id |
| approved_by | UUID | FK users.id |
| status | ENUM | pending, approved, rejected |
| comments | TEXT | NULL |
| requested_at | TIMESTAMP | NOT NULL |
| decided_at | TIMESTAMP | NULL |

### Relationships

Belongs to:

- Ticket
- User (requester)
- User (approver)

---

## audit_logs

Immutable audit history.

Every business action inserts one row.

Examples:

- Ticket created
- AI generated response
- Supervisor approved
- Status changed
- Customer notified

### Columns

| Column | Type | Constraints |
|---------|------|-------------|
| id | UUID | PK |
| ticket_id | UUID | FK tickets.id |
| user_id | UUID | FK users.id NULL |
| event_type | VARCHAR(100) | NOT NULL |
| description | TEXT | NOT NULL |
| metadata | JSONB | NULL |
| created_at | TIMESTAMP | NOT NULL |

### Relationships

Belongs to:

- Ticket
- User (optional)

---

# Indexes

## users

- email (unique)

---

## customers

- email
- company

---

## tickets

- customer_id
- assigned_agent_id
- status
- priority
- created_at

---

## agent_runs

- ticket_id
- created_at
- success

---

## approval_requests

- ticket_id
- status

---

## audit_logs

- ticket_id
- created_at

---

# Cascade Rules

Deleting a customer is prohibited while tickets exist.

Deleting a ticket should never delete audit history.

Deleting users is disabled.
Users become:

```
is_active = false
```

to preserve historical references.

---

# Status Flow

```
NEW
 ↓
TRIAGED
 ↓
ASSIGNED
 ↓
DRAFTED
 ↓
APPROVAL_REQUIRED
 ↓
APPROVED
 ↓
SENT
 ↓
CLOSED
```

---

# User Roles

## Agent

- View assigned tickets
- Generate AI drafts
- Update ticket status

---

## Supervisor

Everything an Agent can do plus:

- Approve responses
- Reject responses
- Reassign tickets
- View all tickets

---

## Admin

Everything plus:

- Manage users
- View audit logs
- Configure platform settings
- System administration

---

# Design Principles

- UUID primary keys for all tables.
- JSONB used for AI inputs, outputs, and metadata.
- Audit logs are immutable.
- Users are soft-deleted using `is_active`.
- Every AI execution is traceable.
- Every approval is recorded.
- Every ticket action is auditable.