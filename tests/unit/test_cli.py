"""Tests for the CLI entry point."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from nl2sql_agent import cli


class TestAskCommand:
    def test_unknown_provider_exits_cleanly(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli._build_agent(provider="unknown")
        assert exc_info.value.code == 2
        assert "unsupported provider" in capsys.readouterr().err.lower()

    def test_runs_question_and_prints_answer(self, capsys):
        # Build a fake agent whose run() returns a known dict.
        fake_agent = MagicMock()
        fake_agent.run.return_value = {
            "final_answer": "There are 10 employees.",
            "sql_query": "SELECT COUNT(*) FROM employees",
        }
        with patch.object(cli, "_build_agent", return_value=fake_agent):
            rc = cli.cmd_ask(cli.build_parser().parse_args(["ask", "how many?"]))
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
            cli.cmd_ask(cli.build_parser().parse_args(["ask", "q", "--show-sql"]))
        captured = capsys.readouterr()
        assert "answer" in captured.out
        assert "--- SQL ---" in captured.out
        assert "SELECT 1" in captured.out

    def test_missing_api_key_returns_2(self):
        from nl2sql_agent.llm import LLMProviderError

        with (
            patch.object(
                cli,
                "_build_agent",
                side_effect=SystemExit(2),
            ),
            patch(
                "nl2sql_agent.llm.build_chat_model",
                side_effect=LLMProviderError("missing key"),
            ),
            pytest.raises(SystemExit),
        ):
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

    def test_redacts_api_keys(self, monkeypatch, capsys):
        monkeypatch.setenv("OPENAI_API_KEY", "super-secret-value")
        monkeypatch.setenv("HF_TOKEN", "hf-super-secret")
        monkeypatch.setenv("XAI_API_KEY", "xai-super-secret")
        monkeypatch.setenv("AGNES_API_KEY", "agnes-super-secret")
        from nl2sql_agent.config import reset_settings_cache

        reset_settings_cache()
        cli.cmd_config(cli.build_parser().parse_args(["config"]))
        out = capsys.readouterr().out
        assert "super-secret-value" not in out
        assert "hf-super-secret" not in out
        assert "xai-super-secret" not in out
        assert "agnes-super-secret" not in out
        assert json.loads(out)["openai_api_key"] == "***"
        assert json.loads(out)["hf_token"] == "***"
        assert json.loads(out)["xai_api_key"] == "***"
        assert json.loads(out)["agnes_api_key"] == "***"


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

    def test_serve_rejects_non_loopback_host(self):
        args = cli.build_parser().parse_args(["serve", "--host", "0.0.0.0"])
        with pytest.raises(SystemExit, match="loopback"):
            cli.cmd_serve(args)

    def test_eval_defaults(self):
        args = cli.build_parser().parse_args(["eval"])
        assert args.min_pass_rate == 0.8
        assert args.dataset is None

    def test_eval_rejects_invalid_pass_rate(self):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["eval", "--min-pass-rate", "1.5"])


class TestEvalCommand:
    def test_writes_report_and_returns_success(self, tmp_path, seeded_db):
        dataset = tmp_path / "cases.jsonl"
        dataset.write_text(
            json.dumps(
                {
                    "id": "count",
                    "question": "count",
                    "expected_outcome": "result",
                    "reference_sql": "SELECT COUNT(*) FROM employees",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        output = tmp_path / "report.json"
        fake_agent = MagicMock()
        fake_agent.db = seeded_db
        fake_agent.run.return_value = {
            "raw_rows": [(10,)],
            "error": "",
            "sql_safe": True,
        }
        args = cli.build_parser().parse_args(
            [
                "eval",
                "--dataset",
                str(dataset),
                "--output",
                str(output),
            ]
        )
        with patch.object(cli, "_build_agent", return_value=fake_agent):
            assert cli.cmd_eval(args) == 0
        assert json.loads(output.read_text(encoding="utf-8"))["result_accuracy"] == 1.0

    def test_returns_failure_below_threshold(self, tmp_path, seeded_db):
        dataset = tmp_path / "cases.jsonl"
        dataset.write_text(
            json.dumps(
                {
                    "id": "count",
                    "question": "count",
                    "expected_outcome": "result",
                    "reference_sql": "SELECT COUNT(*) FROM employees",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        fake_agent = MagicMock()
        fake_agent.db = seeded_db
        fake_agent.run.return_value = {"raw_rows": [(9,)], "error": ""}
        args = cli.build_parser().parse_args(
            [
                "eval",
                "--dataset",
                str(dataset),
                "--output",
                str(tmp_path / "report.json"),
            ]
        )
        with patch.object(cli, "_build_agent", return_value=fake_agent):
            assert cli.cmd_eval(args) == 1
