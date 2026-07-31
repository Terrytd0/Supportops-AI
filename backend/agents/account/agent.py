"""Account specialist agent: account settings, profile, permissions, access, user management."""

from __future__ import annotations

from backend.agents.base import SpecialistAgent


class AccountAgent(SpecialistAgent):
    """Handles account settings, profile, permission, and access-management tickets."""

    ROLE = "Account Support Specialist"
    GOAL = (
        "Help customers manage account settings, profile information, "
        "permissions, and access issues securely and correctly."
    )
    BACKSTORY = (
        "You are an account support specialist at SupportOps AI, responsible "
        "for helping customers with account settings, profile updates, "
        "permission changes, and access/user-management requests, always "
        "following the principle of least privilege and never bypassing "
        "identity verification."
    )
    CATEGORY = "account"
