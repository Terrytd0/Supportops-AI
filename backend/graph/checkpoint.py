"""Redis-backed workflow-execution checkpoints.

This is *not* LangGraph's native checkpointer
(`langgraph.checkpoint.base.BaseCheckpointSaver`): the official Redis-backed
implementation (`langgraph-checkpoint-redis`) requires the RedisJSON +
RediSearch modules (Redis Stack, not the plain `redis:7-alpine` this project
runs) and pulls in a heavy, unrelated dependency chain (`redisvl`,
`ml_dtypes`, ...) for full time-travel replay this project doesn't need.
What's actually asked for -- "what stage did this ticket's workflow reach,
and what did it look like" for diagnostics and best-effort recovery -- is
implemented directly here, on top of `backend.core.redis_client`, per
"avoid unnecessary complexity" over reaching for a heavyweight package.

One evolving Redis key per `ticket_id`, overwritten after each of
`classify_ticket_node` / `select_agent_node` / `execute_agent_node` /
`confidence_evaluation_node` (see `backend/graph/nodes.py`) -- so a crash
mid-workflow leaves the *last completed stage's* snapshot recoverable, not a
full per-stage history. Fails open: a save or read failure is logged and
treated as "no checkpoint," never raised -- checkpoints are diagnostic/
best-effort, never required for correctness (permanent ticket data lives in
PostgreSQL; see docs/architecture.md).

"Resumable after interruption whenever practical" (the sprint's own
qualifier) means: `get_latest()` tells a future recovery path or an
operator which stage a ticket last completed and with what state, so the
workflow *could* be re-entered close to where it left off. Actually
re-invoking `backend.graph.workflow.get_graph()` mid-flight from a
checkpoint is a further step this module deliberately doesn't take --
that's a graph-topology change (skipping already-completed nodes), which is
explicitly out of scope here.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.core.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "workflow_checkpoint"


@dataclass(frozen=True)
class WorkflowCheckpoint:
    """A single recovered checkpoint: the stage last completed and its snapshot."""

    ticket_id: uuid.UUID
    stage: str
    snapshot: dict[str, Any]
    saved_at: datetime


class WorkflowCheckpointStore:
    """Save/load the latest execution checkpoint for a ticket's workflow run."""

    def __init__(self, client: Redis, *, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    def _key(self, ticket_id: uuid.UUID) -> str:
        return f"{_KEY_PREFIX}:{ticket_id}"

    async def save(self, *, ticket_id: uuid.UUID, stage: str, snapshot: dict[str, Any]) -> None:
        """Overwrite `ticket_id`'s checkpoint with `stage`'s snapshot. Never raises."""
        payload = {
            "stage": stage,
            "snapshot": snapshot,
            "saved_at": datetime.now(UTC).isoformat(),
        }
        try:
            await self._client.set(
                self._key(ticket_id), json.dumps(payload, default=str), ex=self._ttl_seconds
            )
        except RedisError as exc:
            logger.warning(
                "Failed to save workflow checkpoint",
                extra={"ticket_id": str(ticket_id), "stage": stage, "error": str(exc)},
            )

    async def get_latest(self, ticket_id: uuid.UUID) -> WorkflowCheckpoint | None:
        """Return `ticket_id`'s last saved checkpoint, or `None` (miss or failure)."""
        try:
            raw = await self._client.get(self._key(ticket_id))
        except RedisError as exc:
            logger.warning(
                "Failed to read workflow checkpoint",
                extra={"ticket_id": str(ticket_id), "error": str(exc)},
            )
            return None

        if raw is None:
            return None

        try:
            payload = json.loads(raw)
            return WorkflowCheckpoint(
                ticket_id=ticket_id,
                stage=payload["stage"],
                snapshot=payload["snapshot"],
                saved_at=datetime.fromisoformat(payload["saved_at"]),
            )
        except (TypeError, ValueError, KeyError):
            logger.warning(
                "Workflow checkpoint payload was malformed", extra={"ticket_id": str(ticket_id)}
            )
            return None
