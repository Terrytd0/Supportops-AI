"""SQLAlchemy ORM models.

Every model is imported here so `Base.metadata` is fully populated as soon
as this package is imported — SQLAlchemy only registers a table once its
model class has been imported, and Alembic autogenerate (next milestone)
needs the complete set.
"""

from backend.database.models.agent_run import AgentRun
from backend.database.models.approval_request import ApprovalRequest
from backend.database.models.audit_log import AuditLog
from backend.database.models.customer import Customer
from backend.database.models.knowledge_article import KnowledgeArticle
from backend.database.models.ticket import Ticket
from backend.database.models.user import User

__all__ = [
    "AgentRun",
    "ApprovalRequest",
    "AuditLog",
    "Customer",
    "KnowledgeArticle",
    "Ticket",
    "User",
]
