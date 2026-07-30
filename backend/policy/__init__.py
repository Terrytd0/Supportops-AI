"""Business rules, guardrails, and routing/escalation policy.

`rules.py` implements deterministic, keyword-based escalation policy
(`evaluate_policy`), consumed by `backend.graph.nodes.confidence_evaluation_node`.

TODO: implement routing policy (which agent handles a given request) and
additional safety/guardrail checks beyond human-review escalation.
"""
