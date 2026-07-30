"""Centralized logging configuration, shared by every part of the application.

`configure_logging()` installs one formatted `StreamHandler` on the root
logger; `get_logger(name)` is a thin wrapper around `logging.getLogger` so
call sites don't import `logging` directly and every module ends up on the
same handler/formatter. Call `configure_logging()` exactly once, from
`backend/main.py` at application startup — every other module only ever
calls `get_logger(__name__)`.

Never log secrets: passwords, JWTs/access tokens, API keys, or raw request
bodies. Log identifiers (ticket/user IDs, emails, event types) instead of
the sensitive payloads themselves.

TODO: source the log level from `backend/config/settings.py` once a
dedicated `log_level` setting exists (currently always INFO).
TODO: switch to a JSON formatter once a log-aggregation target (e.g.
CloudWatch, Datadog) is chosen.
"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Install a formatted stdout handler on the root logger.

    Idempotent: only the first call installs a handler, so it's safe to call
    from multiple entry points (e.g. the app and a script) without
    duplicating log lines.

    Args:
        level: Minimum level the root logger emits. Defaults to INFO.
    """
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return the logger for `name`, sharing the app-wide handler/formatter.

    Callers should pass `__name__` so log lines are attributable to the
    emitting module via the `%(name)s` field in `_LOG_FORMAT`.
    """
    return logging.getLogger(name)
