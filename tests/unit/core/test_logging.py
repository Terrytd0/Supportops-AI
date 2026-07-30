"""Unit tests for the centralized logging configuration."""

import logging

from backend.core.logging import configure_logging, get_logger


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("backend.core.test_logging")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "backend.core.test_logging"


def test_configure_logging_installs_handler_once() -> None:
    root = logging.getLogger()
    handlers_before = list(root.handlers)

    configure_logging()
    handlers_after_first_call = list(root.handlers)

    configure_logging()
    handlers_after_second_call = list(root.handlers)

    assert len(handlers_after_first_call) >= len(handlers_before)
    assert handlers_after_first_call == handlers_after_second_call
