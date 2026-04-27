"""Utils: structured logging via structlog."""

from __future__ import annotations

import logging
import sys

import structlog


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger for ACTosha.

    Args:
        name: Optional logger name (typically __name__ of the calling module).

    Returns:
        Configured structlog BoundLogger.
    """
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(name)


__all__ = ["get_logger"]