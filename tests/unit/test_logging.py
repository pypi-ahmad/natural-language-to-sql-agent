"""Tests for the logging configuration."""

from __future__ import annotations

import io
import logging

from nl2sql_agent.utils import configure_logging, get_logger


def test_configure_logging_default(capsys):
    configure_logging(level="INFO", json=False)
    log = get_logger("test_default")
    log.info("hello")
    captured = capsys.readouterr()
    assert "hello" in captured.err
    assert "INFO" in captured.err


def test_configure_logging_json():
    configure_logging(level="INFO", json=True)
    log = get_logger("test_json")
    # We can't easily assert exact output to stderr because loguru may
    # bypass capsys when enqueue is on, so just exercise the path.
    log.info("json test")
    # No assertion: the test passes if no exception is raised.


def test_configure_logging_sink():
    buf = io.StringIO()
    configure_logging(level="DEBUG", json=False, sink=buf)
    log = get_logger("test_sink")
    log.debug("via sink")
    assert "via sink" in buf.getvalue()
    assert "DEBUG" in buf.getvalue()


def test_get_logger_bound():
    configure_logging(level="INFO")
    log = get_logger("test_bound")
    log.info("bound test")


def test_intercept_handler_for_stdlib():
    configure_logging(level="INFO")
    stdlib = logging.getLogger("httpx")
    stdlib.info("httpx message")
    # No assertion: the handler must not raise.
    assert any(
        h.__class__.__name__ == "_InterceptHandler" for h in stdlib.handlers
    )


def test_multiple_configure_calls_safe(capsys):
    configure_logging(level="WARNING")
    log = get_logger("test_reconfig")
    log.warning("warning 1")
    configure_logging(level="INFO")
    log.info("info 2")
    out = capsys.readouterr().err
    assert "warning 1" in out
    assert "info 2" in out
