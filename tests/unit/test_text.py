"""Tests for text utility helpers."""

from __future__ import annotations

from nl2sql_agent.utils.text import strip_sql_fences, truncate


class TestStripSqlFences:
    def test_bare_sql(self):
        assert strip_sql_fences("SELECT 1") == "SELECT 1"

    def test_strips_markdown_fence_with_lang(self):
        sql = "```sql\nSELECT * FROM users\n```"
        assert strip_sql_fences(sql) == "SELECT * FROM users"

    def test_strips_markdown_fence_no_lang(self):
        sql = "```\nSELECT * FROM users\n```"
        assert strip_sql_fences(sql) == "SELECT * FROM users"

    def test_strips_trailing_semicolon(self):
        assert strip_sql_fences("SELECT 1;") == "SELECT 1"

    def test_strips_trailing_semicolons(self):
        assert strip_sql_fences("SELECT 1;;;") == "SELECT 1"

    def test_strips_quotes(self):
        assert strip_sql_fences('"SELECT 1"') == "SELECT 1"
        assert strip_sql_fences("'SELECT 1'") == "SELECT 1"

    def test_strips_leading_label(self):
        assert strip_sql_fences("SQL: SELECT 1") == "SELECT 1"
        assert strip_sql_fences("Query: SELECT 1") == "SELECT 1"
        assert strip_sql_fences("Here is the SQL SELECT 1") == "SELECT 1"

    def test_empty(self):
        assert strip_sql_fences("") == ""
        assert strip_sql_fences("   ") == ""

    def test_multiline(self):
        sql = "```sql\nSELECT *\nFROM users\nWHERE id = 1\n```"
        assert strip_sql_fences(sql) == "SELECT *\nFROM users\nWHERE id = 1"


class TestTruncate:
    def test_shorter(self):
        assert truncate("hi", 100) == "hi"

    def test_exact(self):
        assert truncate("hello", 5) == "hello"

    def test_truncates_with_suffix(self):
        assert truncate("hello world", 8) == "hello..."

    def test_custom_suffix(self):
        assert truncate("hello world", 8, suffix="…") == "hello w…"

    def test_zero_max(self):
        assert truncate("hi", 0) == "hi"

    def test_negative_max(self):
        assert truncate("hi", -1) == "hi"
