"""Representative support-ticket payloads used by `backend.scripts.load_test`.

Kept separate from the load test's execution logic so the sample dataset can
be scanned/edited without wading through asyncio/httpx code -- the same
data/logic split `backend/scripts/seed.py` uses for its own seed data.
"""

from __future__ import annotations

from typing import TypedDict


class LoadTestTicket(TypedDict):
    title: str
    description: str


TICKETS: list[LoadTestTicket] = [
    {
        "title": "Billing issue",
        "description": "I was charged twice.",
    },
    {
        "title": "Password reset",
        "description": "Cannot access my account.",
    },
    {
        "title": "API error",
        "description": "Receiving a 500 error.",
    },
    {
        "title": "Refund request",
        "description": "I'd like a refund.",
    },
    {
        "title": "Login failure",
        "description": "Getting 'invalid credentials' even after resetting my password.",
    },
    {
        "title": "Feature request",
        "description": "Please add bulk CSV export for tickets.",
    },
]
