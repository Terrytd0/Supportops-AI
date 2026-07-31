"""Deterministic policy evaluation for human-review escalation.

`evaluate_policy` is the single function `backend/graph/nodes.py::
confidence_evaluation_node` delegates to, so the node stays a thin adapter
and this module stays the one place business rules for human review live
(per CLAUDE.md: "Keep agent, graph, and policy concerns separate ... policy
defines business rules"). It remains deterministic and model-free itself:
every rule is a plain keyword match, a regex over dollar figures, a
threshold comparison, or -- for `agent_unresolved` -- a boolean already
decided upstream. No rule here calls a model or a repository directly;
`agent_unresolved` is how a CrewAI agent's own (OpenAI-informed) judgment
reaches this function, as a reported signal rather than a decision agents
make for themselves.

TODO(Repository): source per-tenant policy thresholds (e.g. the refund
amount threshold) from a repository/config table instead of the module
constants below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Keywords that unconditionally require human review when found in the
# ticket text (case-insensitive substring match). Deliberately flat and
# unordered: unlike backend/graph/nodes.py's classification rules, review
# escalation is not first-match-wins — every matching keyword is reported.
_ESCALATION_KEYWORDS: tuple[str, ...] = (
    "legal",
    "lawsuit",
    "attorney",
    "security",
    "breach",
    "fraud",
)

# Refund mentions always require review; a detected dollar amount above this
# placeholder threshold is additionally flagged as "refund_over_threshold"
# for a more specific audit reason. TODO(Repository): move to per-tenant
# config once policy thresholds are persisted.
_REFUND_KEYWORD = "refund"
_REFUND_AMOUNT_THRESHOLD_USD = 500.0
_DOLLAR_AMOUNT_PATTERN = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)")

# Below this confidence score, a ticket requires review regardless of
# keyword matches. TODO: replace with a real, model-derived confidence
# score once execute_agent_node/classify_ticket_node call OpenAI; today
# every caller passes a constant placeholder score.
_LOW_CONFIDENCE_THRESHOLD = 0.7


@dataclass(frozen=True)
class PolicyEvaluation:
    """Structured result of a single `evaluate_policy` call.

    `matched_rules` lists every rule that fired (e.g. `"refund"`,
    `"low_confidence"`), so callers/audit logging can report *why* a ticket
    was escalated, not just that it was.
    """

    requires_human_review: bool
    matched_rules: tuple[str, ...]
    reason: str


def _matched_keyword_rules(ticket_text: str) -> list[str]:
    """Return every escalation keyword found in `ticket_text`, plus refund rules."""
    text = ticket_text.lower()
    matched = [keyword for keyword in _ESCALATION_KEYWORDS if keyword in text]

    if _REFUND_KEYWORD in text:
        matched.append(_REFUND_KEYWORD)
        if _has_amount_over_threshold(text):
            matched.append("refund_over_threshold")

    return matched


def _has_amount_over_threshold(text: str) -> bool:
    """Return True if any dollar figure in `text` exceeds the refund threshold."""
    for match in _DOLLAR_AMOUNT_PATTERN.finditer(text):
        amount = float(match.group(1).replace(",", ""))
        if amount > _REFUND_AMOUNT_THRESHOLD_USD:
            return True
    return False


def _build_reason(matched_rules: list[str]) -> str:
    """Render a human-readable audit reason from the matched rule names."""
    if not matched_rules:
        return "No escalation rules matched; eligible for automated response."
    return f"Escalation rules matched: {', '.join(matched_rules)}."


def evaluate_policy(
    ticket_text: str,
    confidence_score: float,
    agent_unresolved: bool = False,
) -> PolicyEvaluation:
    """Determine whether a ticket requires human/supervisor review.

    Placeholder business rules, all keyword-, threshold-, or signal-based:
    - Escalation keywords: legal, lawsuit, attorney, security, breach, fraud.
    - Refund mentions (always), flagged additionally as
      "refund_over_threshold" when a dollar amount over
      `_REFUND_AMOUNT_THRESHOLD_USD` is present.
    - Confidence below `_LOW_CONFIDENCE_THRESHOLD`.
    - `agent_unresolved` (see below).

    Args:
        ticket_text: Raw ticket text, as stored on `WorkflowState.ticket_text`.
        confidence_score: The workflow's current confidence score (0.0-1.0).
        agent_unresolved: The specialist agent's own structured "I couldn't
            confidently resolve this" signal (`AgentResult.unresolved`, set
            on a CrewAI/OpenAI failure or the agent's own judgment -- see
            `backend.agents.base.SpecialistAgent`). This is this function's
            entire contract with the agent layer: agents report an outcome,
            this function is the only place that turns it into an escalation
            decision.

    Returns:
        A `PolicyEvaluation` with `requires_human_review` set if any rule matched.
    """
    matched_rules = _matched_keyword_rules(ticket_text)

    if confidence_score < _LOW_CONFIDENCE_THRESHOLD:
        matched_rules.append("low_confidence")

    if agent_unresolved:
        matched_rules.append("agent_unresolved")

    return PolicyEvaluation(
        requires_human_review=bool(matched_rules),
        matched_rules=tuple(matched_rules),
        reason=_build_reason(matched_rules),
    )
