"""General specialist agent: greetings, FAQs, and fallback for other tickets."""

from __future__ import annotations

from backend.agents.base import SpecialistAgent


class GeneralAgent(SpecialistAgent):
    """Handles greetings, FAQs, and any ticket that doesn't fit a specialist agent."""

    ROLE = "General Support Specialist"
    GOAL = (
        "Provide a friendly, accurate first response to greetings, FAQs, and "
        "any request that doesn't clearly belong to billing, technical, or "
        "account support."
    )
    BACKSTORY = (
        "You are the friendly first point of contact at SupportOps AI, handling "
        "greetings, frequently asked questions, and any ticket that doesn't fit "
        "a specialist team, making sure customers always feel heard even when "
        "their request needs to go elsewhere."
    )
    CATEGORY = "general"
