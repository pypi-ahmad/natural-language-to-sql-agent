"""Tests for the CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nl2sql_agent import cli


class TestAskCommand:
    def test_runs_question_and_prints_answer(self, capsys):
        # Build a fake agent whose run() returns a known dict.
        fake_agent = MagicMock()
        fake_agent.run.return_value = {
            "final_answer": "There are 10 employees.",
            "sql_query": "SELECT COUNT(*) FROM employees",
        }
        with patch.object(cli, "_build_agent", return_value=fake_agent):
            rc = cli.cmd_ask(
                cli.build_parser().parse_args(
                    ["ask", "how many?"]
                )
            )
        assert rc == 0
        captured = capsys.readouterr()
        assert "There are 10 employees." in captured.out
        assert "SELECT COUNT" not in captured.out  # not shown without --show-sql

    def test_show_sql_prints_sql(self, capsys):
        fake_agent = MagicMock()
        fake_agent.run.return_value = {
            "final_answer": "answer",
            "sql_query": "SELECT 1",
        }
        with patch.object(cli, "_build_agent", return_value=fake_agent):
            cli.cmd_ask(
                cli.build_parser().parse_args(["ask", "q", "--show-sql"])
            )
        captured = capsys.readouterr()
        assert "answer" in captured.out
        assert "--- SQL ---" in captured.out
        assert "SELECT 1" in captured.out

    def test_missing_api_key_returns_2(self):
        from nl2sql_agent.llm import LLMProviderError

        with patch.object(
            cli,
            "_build_agent",
            side_effect=SystemExit(2),
        ), patch(
            "nl2sql_agent.llm.build_chat_model",
            side_effect=LLMProviderError("missing key"),
        ), pytest.raises(SystemExit):
            cli.cmd_ask(cli.build_parser().parse_args(["ask", "q"]))


class TestConfigCommand:
    def test_prints_settings_json(self, capsys, monkeypatch):
        for v in ("NL2SQL_PROVIDER",):
            monkeypatch.delenv(v, raising=False)
        from nl2sql_agent.config import reset_settings_cache
        reset_settings_cache()
        rc = cli.cmd_config(cli.build_parser().parse_args(["config"]))
        assert rc == 0
        out = capsys.readouterr().out
        # Should be valid JSON with the provider key.
        import json
        data = json.loads(out)
        assert "provider" in data
        assert "model" in data


class TestParser:
    def test_no_command_fails(self):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args([])

    def test_ask_requires_question(self):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["ask"])

    def test_serve_defaults(self):
        args = cli.build_parser().parse_args(["serve"])
        assert args.port == 8501
        assert args.host == "127.0.0.1"
