"""Tests for the prompt templates."""

from __future__ import annotations

from nl2sql_agent.prompts import (
    SQL_WRITER_SYSTEM,
    SQL_WRITER_USER,
    SUMMARIZER_USER,
    error_section,
    format_data,
)


class TestPrompts:
    def test_writer_system_includes_safety_rules(self):
        assert "SELECT" in SQL_WRITER_SYSTEM
        assert "DROP" in SQL_WRITER_SYSTEM
        assert "INSERT" in SQL_WRITER_SYSTEM

    def test_writer_user_has_placeholders(self):
        assert "{schema}" in SQL_WRITER_USER
        assert "{question}" in SQL_WRITER_USER
        assert "{error_section}" in SQL_WRITER_USER

    def test_summarizer_user_has_placeholders(self):
        assert "{question}" in SUMMARIZER_USER
        assert "{sql}" in SUMMARIZER_USER
        assert "{data}" in SUMMARIZER_USER
        assert "{error}" in SUMMARIZER_USER

    def test_error_section_empty(self):
        assert error_section(None) == ""
        assert error_section("") == ""

    def test_error_section_formatted(self):
        out = error_section("syntax error")
        assert "syntax error" in out
        assert "previous attempt failed" in out

    def test_format_data_empty(self):
        assert format_data("") == "(no rows)"
        assert format_data("No data found.") == "(no rows)"

    def test_format_data_short(self):
        assert format_data("foo") == "foo"

    def test_format_data_truncates(self):
        big = "x" * 5000
        out = format_data(big)
        assert len(out) < 5000
        assert "truncated" in out

    def test_writer_user_renders(self):
        out = SQL_WRITER_USER.format(
            schema="employees(id, name)",
            question="how many?",
            error_section=error_section(None),
        )
        assert "employees" in out
        assert "how many?" in out

    def test_summarizer_user_renders(self):
        out = SUMMARIZER_USER.format(
            question="q", sql="SELECT 1", data="1", error="",
        )
        assert "SELECT 1" in out
        assert "1" in out
