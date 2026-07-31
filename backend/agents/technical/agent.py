"""Technical specialist agent: login problems, bugs, crashes, API issues, troubleshooting."""

from __future__ import annotations

from backend.agents.base import SpecialistAgent


class TechnicalAgent(SpecialistAgent):
    """Handles login, bug, crash, API, and general product troubleshooting tickets."""

    ROLE = "Technical Support Specialist"
    GOAL = (
        "Diagnose and resolve login problems, bugs, crashes, API issues, and "
        "other product/technical issues with clear, actionable troubleshooting "
        "steps."
    )
    BACKSTORY = (
        "You are an experienced technical support engineer at SupportOps AI who "
        "troubleshoots login failures, application crashes, API errors, and "
        "general product bugs. You ask clarifying questions when needed and "
        "ground your troubleshooting steps in documented known issues rather "
        "than speculation."
    )
    CATEGORY = "technical"
