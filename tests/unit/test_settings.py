"""Tests for the settings module."""

from __future__ import annotations

from pathlib import Path

import pytest

from nl2sql_agent.config import (
    Settings,
    env_var_for,
    env_var_value,
    get_settings,
    reset_settings_cache,
)


class TestSettings:
    def test_defaults(self, monkeypatch):
        for var in (
            "NL2SQL_PROVIDER", "NL2SQL_MODEL", "OPENAI_API_KEY",
            "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        reset_settings_cache()
        s = get_settings()
        assert s.provider == "ollama"
        assert s.model == "phi4-mini:3.8b"
        assert s.db_seed is True
        assert s.max_retries == 3
        assert s.log_level == "INFO"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("NL2SQL_PROVIDER", "openai")
        monkeypatch.setenv("NL2SQL_MODEL", "gpt-4o-mini")
        reset_settings_cache()
        s = get_settings()
        assert s.provider == "openai"
        assert s.model == "gpt-4o-mini"

    def test_provider_lowercased(self, monkeypatch):
        monkeypatch.setenv("NL2SQL_PROVIDER", "Anthropic")
        reset_settings_cache()
        assert get_settings().provider == "anthropic"

    def test_db_path_coerced_from_string(self, monkeypatch):
        monkeypatch.setenv("NL2SQL_DB_PATH", "/tmp/x.db")
        reset_settings_cache()
        assert get_settings().db_path == Path("/tmp/x.db")

    def test_model_must_not_be_empty(self, monkeypatch):
        monkeypatch.setenv("NL2SQL_MODEL", "   ")
        reset_settings_cache()
        with pytest.raises(ValueError):
            get_settings()

    def test_max_retries_bounded(self, monkeypatch):
        monkeypatch.setenv("NL2SQL_MAX_RETRIES", "100")
        reset_settings_cache()
        with pytest.raises(ValueError):
            get_settings()

    def test_api_key_for(self, monkeypatch):
        s = Settings(openai_api_key="k1", google_api_key="k2", anthropic_api_key="k3")
        assert s.api_key_for("openai") == "k1"
        assert s.api_key_for("gemini") == "k2"
        assert s.api_key_for("anthropic") == "k3"
        assert s.api_key_for("ollama") is None

    def test_settings_is_singleton(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "NL2SQL_MODEL"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        a = get_settings()
        b = get_settings()
        assert a is b

    def test_reset_clears_cache(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "NL2SQL_MODEL"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        a = get_settings()
        reset_settings_cache()
        b = get_settings()
        assert a is not b


class TestEnvVar:
    def test_env_var_for(self):
        assert env_var_for("openai") == "OPENAI_API_KEY"
        assert env_var_for("gemini") == "GOOGLE_API_KEY"
        assert env_var_for("anthropic") == "ANTHROPIC_API_KEY"
        assert env_var_for("ollama") is None

    def test_env_var_value(self, monkeypatch):
        assert env_var_value("DOES_NOT_EXIST") is None
        monkeypatch.setenv("MY_VAR", "value")
        assert env_var_value("MY_VAR") == "value"
        monkeypatch.setenv("MY_VAR", "  ")
        assert env_var_value("MY_VAR") is None
