"""Tests for the settings module."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from nl2sql_agent.config import (
    Settings,
    default_model_for,
    env_var_for,
    env_var_value,
    get_settings,
    reset_settings_cache,
    supported_models_for,
)


class TestSettings:
    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com:11434",
            "ftp://localhost:11434",
            "http://user:pass@localhost:11434",
        ],
    )
    def test_rejects_unsafe_ollama_url(self, url):
        with pytest.raises(ValidationError):
            Settings(ollama_base_url=url)

    def test_allows_https_remote_ollama_url(self):
        url = "https://ollama.example.com"
        assert Settings(ollama_base_url=url).ollama_base_url == url

    def test_defaults(self, monkeypatch):
        for var in (
            "NL2SQL_PROVIDER",
            "NL2SQL_MODEL",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY",
            "ANTHROPIC_API_KEY",
            "HF_TOKEN",
            "XAI_API_KEY",
        ):
            monkeypatch.delenv(var, raising=False)
        reset_settings_cache()
        s = get_settings()
        assert s.provider == "ollama"
        assert s.model == "phi4-mini:3.8b"
        assert s.db_seed is True
        assert s.max_retries == 3
        assert s.log_level == "INFO"
        assert s.db_upload_max_mb == 50
        assert s.db_max_vm_steps == 5_000_000
        assert s.schema_max_tables == 8
        assert s.sql_max_joins == 8
        assert s.audit_enabled is True
        assert s.hf_token is None
        assert s.xai_api_key is None

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("NL2SQL_PROVIDER", "openai")
        monkeypatch.setenv("NL2SQL_MODEL", "gpt-5.6-luna")
        reset_settings_cache()
        s = get_settings()
        assert s.provider == "openai"
        assert s.model == "gpt-5.6-luna"

    def test_provider_lowercased(self, monkeypatch):
        monkeypatch.setenv("NL2SQL_PROVIDER", "Anthropic")
        monkeypatch.setenv("NL2SQL_MODEL", "claude-sonnet-5")
        reset_settings_cache()
        assert get_settings().provider == "anthropic"

    @pytest.mark.parametrize(
        ("provider", "expected"),
        [
            ("openai", "gpt-5.6-luna"),
            ("anthropic", "claude-sonnet-5"),
            ("gemini", "gemini-3.7-flash"),
            ("xai", "grok-4.6"),
            ("huggingface", "openai/gpt-oss-120b:fastest"),
        ],
    )
    def test_provider_uses_its_default_model_when_model_is_omitted(self, provider, expected):
        assert Settings(_env_file=None, provider=provider).model == expected

    @pytest.mark.parametrize(
        ("provider", "model"),
        [
            ("openai", "gpt-4o"),
            ("anthropic", "claude-3-5-sonnet-latest"),
            ("gemini", "gemini-2.0-flash"),
            ("xai", "grok-4.5"),
            ("huggingface", "not-a-repository-id"),
        ],
    )
    def test_rejects_unapproved_cloud_model(self, provider, model):
        with pytest.raises(ValidationError, match="model"):
            Settings(_env_file=None, provider=provider, model=model)

    def test_accepts_custom_hugging_face_model(self):
        settings = Settings(
            _env_file=None,
            provider="huggingface",
            model="Qwen/Qwen3-Coder-480B-A35B-Instruct:fastest",
        )
        assert settings.model == "Qwen/Qwen3-Coder-480B-A35B-Instruct:fastest"

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
        s = Settings(
            openai_api_key="k1",  # pragma: allowlist secret
            google_api_key="k2",  # pragma: allowlist secret
            anthropic_api_key="k3",  # pragma: allowlist secret
            hf_token="k4",
            xai_api_key="k5",  # pragma: allowlist secret
        )
        assert s.api_key_for("openai") == "k1"
        assert s.api_key_for("gemini") == "k2"
        assert s.api_key_for("anthropic") == "k3"
        assert s.api_key_for("huggingface") == "k4"
        assert s.api_key_for("xai") == "k5"
        assert s.api_key_for("ollama") is None

    def test_cloud_model_catalog(self):
        assert supported_models_for("openai") == ("gpt-5.6-luna", "gpt-5.6-terra")
        assert supported_models_for("anthropic") == ("claude-sonnet-5",)
        assert supported_models_for("gemini") == (
            "gemini-3.7-flash",
            "gemini-3.5-flash-lite",
        )
        assert supported_models_for("xai") == ("grok-4.6",)
        assert default_model_for("huggingface") == "openai/gpt-oss-120b:fastest"

    def test_standard_cloud_key_environment_variables(self, monkeypatch):
        monkeypatch.setenv("HF_TOKEN", "hf-secret")
        monkeypatch.setenv("XAI_API_KEY", "xai-secret")
        settings = Settings(_env_file=None)
        assert settings.hf_token == "hf-secret"
        assert settings.xai_api_key == "xai-secret"  # pragma: allowlist secret

    def test_prefixed_cloud_key_environment_variables(self, monkeypatch):
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        monkeypatch.setenv("NL2SQL_HF_TOKEN", "hf-prefixed")
        monkeypatch.setenv("NL2SQL_XAI_API_KEY", "xai-prefixed")
        settings = Settings(_env_file=None)
        assert settings.hf_token == "hf-prefixed"
        assert settings.xai_api_key == "xai-prefixed"  # pragma: allowlist secret

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
        assert env_var_for("huggingface") == "HF_TOKEN"
        assert env_var_for("xai") == "XAI_API_KEY"
        assert env_var_for("ollama") is None

    def test_env_var_value(self, monkeypatch):
        assert env_var_value("DOES_NOT_EXIST") is None
        monkeypatch.setenv("MY_VAR", "value")
        assert env_var_value("MY_VAR") == "value"
        monkeypatch.setenv("MY_VAR", "  ")
        assert env_var_value("MY_VAR") is None
