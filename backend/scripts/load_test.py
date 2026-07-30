"""Concurrency load test: 50 simultaneous ticket-decision requests.

Usage:
    # In one terminal, run the app (see README.md):
    uvicorn backend.main:app

    # In another:
    python -m backend.scripts.load_test

Scope note (Sprint 4 Day 5 Task 4): there is no ticket-*creation* endpoint
yet -- no `POST /tickets` router exists under `backend/api/routes/`, and
adding one is out of scope here (application business logic is untouched).
The nearest workflow-related POST endpoints that do exist are the
supervisor approve/reject decisions in `backend/api/supervisor.py`, so this
measures the concurrency characteristics of the current HTTP API (routing,
rate limiting, the placeholder queue lookup) via
`POST /supervisor/{ticket_id}/reject`, not the future ticket-ingestion
workflow.

All 50 requests target that single endpoint, so the run also naturally
exercises the 30/minute/IP rate limit configured in
`backend/api/supervisor.py` (Sprint 4 Day 5 Task 3): the first 30 succeed
and the rest are throttled with 429s. Those 429s are expected, correct
behavior under load -- not failures -- and are reported in their own
bucket below rather than bypassing the limiter to avoid them.

Uses only asyncio + httpx.AsyncClient (already a project dependency); no
dedicated load-testing framework.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import os
import time
from dataclasses import dataclass

import httpx

from backend.core.logging import configure_logging, get_logger
from backend.scripts.load_test_tickets import TICKETS, LoadTestTicket

logger = get_logger(__name__)

# Overridable so the test can point at a non-default host/port without code
# changes; defaults to `uvicorn backend.main:app`'s default bind address.
_BASE_URL = os.environ.get("LOAD_TEST_BASE_URL", "http://127.0.0.1:8000")

# Matches the single entry in `backend.api.supervisor._PLACEHOLDER_QUEUE`
# (the same placeholder ID `tests/unit/api/test_supervisor.py` uses) -- the
# only ticket ID the placeholder queue currently recognizes.
_KNOWN_TICKET_ID = "00000000-0000-0000-0000-000000000001"
_ENDPOINT_PATH = f"/supervisor/{_KNOWN_TICKET_ID}/reject"

_CONCURRENT_REQUESTS = 50
_REQUEST_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class _RequestOutcome:
    """Result of one request: either a status code or a transport error."""

    status_code: int | None
    latency_seconds: float | None
    error: str | None = None

    @property
    def is_successful(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300

    @property
    def is_rate_limited(self) -> bool:
        return self.status_code == 429

    @property
    def is_failed(self) -> bool:
        return not (self.is_successful or self.is_rate_limited)


async def _submit_ticket(
    client: httpx.AsyncClient, ticket: LoadTestTicket, request_number: int
) -> _RequestOutcome:
    """POST one ticket decision; never raises so a bad request can't stop the batch."""
    comment = f"[{ticket['title']}] {ticket['description']} (request #{request_number})"
    start = time.perf_counter()
    try:
        response = await client.post(
            _ENDPOINT_PATH, json={"comments": comment}, timeout=_REQUEST_TIMEOUT_SECONDS
        )
    except httpx.HTTPError as exc:
        logger.warning("Request #%d failed: %s", request_number, exc)
        return _RequestOutcome(status_code=None, latency_seconds=None, error=str(exc))

    latency = time.perf_counter() - start
    if response.status_code == 429:
        logger.info("Request #%d rate limited (429)", request_number)
    elif response.status_code >= 400:
        logger.warning("Request #%d returned %d", request_number, response.status_code)
    return _RequestOutcome(status_code=response.status_code, latency_seconds=latency)


def _ticket_batch(count: int) -> list[LoadTestTicket]:
    """Cycle through the sample ticket types to fill `count` requests."""
    return list(itertools.islice(itertools.cycle(TICKETS), count))


async def _run_load_test() -> list[_RequestOutcome]:
    tickets = _ticket_batch(_CONCURRENT_REQUESTS)
    async with httpx.AsyncClient(base_url=_BASE_URL) as client:
        tasks = [
            _submit_ticket(client, ticket, request_number)
            for request_number, ticket in enumerate(tickets, start=1)
        ]
        return await asyncio.gather(*tasks)


def _print_summary(outcomes: list[_RequestOutcome], total_time: float) -> None:
    successful = [o for o in outcomes if o.is_successful]
    rate_limited = [o for o in outcomes if o.is_rate_limited]
    failed = [o for o in outcomes if o.is_failed]
    latencies = [o.latency_seconds for o in outcomes if o.latency_seconds is not None]

    avg_latency_ms = (sum(latencies) / len(latencies)) * 1000 if latencies else 0.0
    min_latency_ms = min(latencies) * 1000 if latencies else 0.0
    max_latency_ms = max(latencies) * 1000 if latencies else 0.0
    throughput = len(outcomes) / total_time if total_time > 0 else 0.0

    separator = "-" * 50
    logger.info(separator)
    logger.info("Load Test Results")
    logger.info(separator)
    logger.info("Concurrent Requests : %d", len(outcomes))
    logger.info("Successful          : %d", len(successful))
    logger.info("Rate Limited (429)  : %d", len(rate_limited))
    logger.info("Failed              : %d", len(failed))
    logger.info("Total Time          : %.2f s", total_time)
    logger.info("Average Latency     : %.0f ms", avg_latency_ms)
    logger.info("Minimum Latency     : %.0f ms", min_latency_ms)
    logger.info("Maximum Latency     : %.0f ms", max_latency_ms)
    logger.info("Throughput          : %.1f req/s", throughput)
    logger.info(separator)

    if failed:
        for outcome in failed:
            logger.warning(
                "Failed request detail: status=%s error=%s", outcome.status_code, outcome.error
            )


def main() -> None:
    """Entry point for `python -m backend.scripts.load_test`."""
    configure_logging()
    # httpx logs one INFO line per request by default, which would drown out
    # our own progress/summary output; keep only our logger at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger.info(
        "Starting load test: %d concurrent requests to %s%s",
        _CONCURRENT_REQUESTS,
        _BASE_URL,
        _ENDPOINT_PATH,
    )
    start = time.perf_counter()
    outcomes = asyncio.run(_run_load_test())
    total_time = time.perf_counter() - start
    _print_summary(outcomes, total_time)


if __name__ == "__main__":
    main()
