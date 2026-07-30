"""Unit tests for deterministic policy evaluation."""

from backend.policy.rules import evaluate_policy


def test_no_rules_matched_allows_automation() -> None:
    result = evaluate_policy(ticket_text="My app keeps crashing on login.", confidence_score=1.0)
    assert result.requires_human_review is False
    assert result.matched_rules == ()


def test_escalation_keyword_requires_review() -> None:
    result = evaluate_policy(
        ticket_text="I'm going to get my attorney involved.", confidence_score=1.0
    )
    assert result.requires_human_review is True
    assert "attorney" in result.matched_rules


def test_refund_mention_requires_review() -> None:
    result = evaluate_policy(
        ticket_text="Please process a refund for my order.", confidence_score=1.0
    )
    assert result.requires_human_review is True
    assert "refund" in result.matched_rules
    assert "refund_over_threshold" not in result.matched_rules


def test_refund_over_threshold_is_flagged_separately() -> None:
    result = evaluate_policy(
        ticket_text="Please refund me $750 for this order.", confidence_score=1.0
    )
    assert result.requires_human_review is True
    assert "refund" in result.matched_rules
    assert "refund_over_threshold" in result.matched_rules


def test_low_confidence_requires_review() -> None:
    result = evaluate_policy(ticket_text="How do I reset my password?", confidence_score=0.2)
    assert result.requires_human_review is True
    assert "low_confidence" in result.matched_rules


def test_case_insensitive_matching() -> None:
    result = evaluate_policy(ticket_text="This is a SECURITY issue.", confidence_score=1.0)
    assert result.requires_human_review is True
    assert "security" in result.matched_rules
