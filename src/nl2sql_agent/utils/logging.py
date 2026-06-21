"""Structured logging via Loguru.

Use ``get_logger(__name__)`` instead of ``logging.getLogger`` to get a
configured logger with the project's preferred format. All loggers inherit
from the singleton configured in :func:`configure_logging`.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger as _loguru_logger


def configure_logging(
    level: str = "INFO",
    *,
    json: bool = False,
    sink: Any = None,
) -> None:
    """Configure Loguru as the project's single logging backend.

    Replaces the default Loguru handler and silences noisy third-party loggers.
    Safe to call multiple times; subsequent calls rebuild the handler.
    """
    if json:
        fmt = (
            '{{"ts":"{time:YYYY-MM-DDTHH:mm:ss.SSSZ}",'
            '"level":"{level}",'
            '"name":"{name}",'
            '"msg":"{message}"}}\n'
        )
    else:
        fmt = (
            "<green>{time:HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>\n"
        )

    _loguru_logger.remove()
    _loguru_logger.add(
        sink or sys.stderr,
        format=fmt,
        level=level.upper(),
        enqueue=False,
        backtrace=False,
        diagnose=False,
    )

    # Route stdlib logging (used by some libraries) to Loguru.
    class _InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            try:
                level_ = _loguru_logger.level(record.levelname).name
            except ValueError:
                level_ = record.levelno  # type: ignore[assignment]
            frame: Any = logging.currentframe()
            depth = 2
            while frame and frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
                level_,
                record.getMessage(),
            )

    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "watchdog"):
        stdlib_logger = logging.getLogger(noisy)
        stdlib_logger.handlers = [_InterceptHandler()]
        stdlib_logger.propagate = False


def get_logger(name: str | None = None) -> Any:
    """Return a Loguru logger bound to ``name`` for traceability."""
    if name:
        return _loguru_logger.bind(logger_name=name)
    return _loguru_logger
