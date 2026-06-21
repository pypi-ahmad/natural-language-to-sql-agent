"""Tests for the LLM provider factory and model discovery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nl2sql_agent.config import get_settings, reset_settings_cache
from nl2sql_agent.llm import (
    LLMProviderError,
    build_chat_model,
    fallback_models,
    list_models,
)


class TestFallbackModels:
    def test_ollama(self):
        assert "phi4-mini:3.8b" in fallback_models("ollama")

    def test_openai(self):
        assert "gpt-4o" in fallback_models("openai")

    def test_gemini(self):
        assert "gemini-1.5-flash" in fallback_models("gemini")

    def test_anthropic(self):
        assert "claude-3-5-sonnet-latest" in fallback_models("anthropic")


class TestListModels:
    def test_ollama_no_connection_returns_empty(self):
        # When ollama is unreachable, list_models should return [].
        with (
            patch("ollama.Client", side_effect=Exception("connection refused")),
            patch("ollama.list", side_effect=Exception("connection refused")),
        ):
            result = list_models("ollama", base_url="http://nope:1")
        assert result == []

    def test_ollama_returns_models(self):
        fake_model = MagicMock()
        fake_model.model = "qwen3.5:4b"
        info = MagicMock()
        info.models = [fake_model]
        with patch("ollama.Client") as Client:
            Client.return_value.list.return_value = info
            result = list_models("ollama", base_url="http://localhost:11434")
        assert "qwen3.5:4b" in result

    def test_openai_without_key_returns_empty(self):
        assert list_models("openai", api_key=None) == []

    def test_gemini_without_key_returns_empty(self):
        assert list_models("gemini", api_key=None) == []

    def test_anthropic_uses_curated_list(self):
        result = list_models("anthropic")
        assert "claude-3-5-sonnet-latest" in result

    def test_unknown_provider_returns_empty(self):
        # list_models accepts only the four we know; unknown should be safe.
        from nl2sql_agent.llm import LLMProviderError

        # The strict provider normalizer raises, so an unknown name no longer
        # silently returns []. Document that contract.
        with pytest.raises(LLMProviderError, match="Unsupported"):
            list_models("unknown_provider")  # type: ignore[arg-type]


class TestBuildChatModel:
    def test_ollama_uses_chat_ollama(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "NL2SQL_MODEL", "NL2SQL_OLLAMA_BASE_URL"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        with patch("langchain_ollama.ChatOllama") as mock_cls:
            mock_cls.return_value = MagicMock()
            llm = build_chat_model(s)
        assert llm is not None
        # Base URL is passed through.
        _, kwargs = mock_cls.call_args
        assert kwargs["base_url"] == s.ollama_base_url

    def test_openai_without_key_raises(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "OPENAI_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "openai"
        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            build_chat_model(s)

    def test_openai_with_key_uses_chat_openai(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "OPENAI_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "openai"
        s.openai_api_key = "sk-test"
        s.model = "gpt-4o-mini"
        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(s)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["model"] == "gpt-4o-mini"

    def test_gemini_without_key_raises(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "GOOGLE_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "gemini"
        with pytest.raises(LLMProviderError, match="GOOGLE_API_KEY"):
            build_chat_model(s)

    def test_anthropic_without_key_raises(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "anthropic"
        with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY"):
            build_chat_model(s)

    def test_unknown_provider_raises(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER",):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "unknown"  # type: ignore[assignment]
        with pytest.raises(LLMProviderError, match="Unsupported"):
            build_chat_model(s)

    def test_ollama_with_dict_response(self):
        # Some ollama versions return a plain dict, not a pydantic object.
        info = {"models": [{"name": "qwen3.5:4b"}, {"name": "llama3"}]}
        with patch("ollama.Client") as Client:
            Client.return_value.list.return_value = info
            with patch("ollama.list", return_value=info):
                result = list_models("ollama", base_url="http://localhost:11434")
        # Either list path may be hit; both should include the model name.
        assert "qwen3.5:4b" in result or "llama3" in result

    def test_temperature_override(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER",):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        with patch("langchain_ollama.ChatOllama") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(s, temperature=0.7, max_tokens=512, model="llama3.1")
        _, kwargs = mock_cls.call_args
        assert kwargs["temperature"] == 0.7
        assert kwargs["num_predict"] == 512
        assert kwargs["model"] == "llama3.1"
