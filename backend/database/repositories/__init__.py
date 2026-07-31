"""Repository pattern data-access layer.

- `knowledge_article.py` — `KnowledgeArticleRepository`, consumed by
  `backend.tools.knowledge_base.KnowledgeBaseSearchTool`.
- `approval_request.py` — `ApprovalRequestRepository`, the supervisor
  queue's data access, consumed by `backend/api/supervisor.py` and
  `backend.graph.nodes.persist_results_node`.
- `audit_log.py` — `AuditLogRepository`, consumed by
  `backend.services.audit.log_audit_event`.

TODO: implement `TicketRepository` -- there's still no repository (or API)
for creating/reading a `Ticket` row itself, so `ApprovalRequestRepository`
today requires one to already exist for its `ticket_id` foreign key.
"""
