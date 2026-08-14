"""Tests for the LLM provider factory and model discovery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nl2sql_agent.config import Settings, get_settings, reset_settings_cache
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
        assert tuple(fallback_models("openai")) == ("gpt-5.6-luna", "gpt-5.6-terra")

    def test_gemini(self):
        assert tuple(fallback_models("gemini")) == (
            "gemini-3.7-flash",
            "gemini-3.5-flash-lite",
        )

    def test_anthropic(self):
        assert tuple(fallback_models("anthropic")) == ("claude-sonnet-5",)

    def test_huggingface(self):
        assert tuple(fallback_models("huggingface")) == ("openai/gpt-oss-120b:fastest",)

    def test_xai(self):
        assert tuple(fallback_models("xai")) == ("grok-4.6",)

    def test_agnes(self):
        assert tuple(fallback_models("agnes")) == ("agnes-2.5-flash",)


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
        Client.return_value.close.assert_called_once_with()

    def test_openai_uses_approved_list_without_key(self):
        assert list_models("openai", api_key=None) == ["gpt-5.6-luna", "gpt-5.6-terra"]

    def test_gemini_uses_approved_list_without_key(self):
        assert list_models("gemini", api_key=None) == [
            "gemini-3.7-flash",
            "gemini-3.5-flash-lite",
        ]

    def test_anthropic_uses_curated_list(self):
        result = list_models("anthropic")
        assert result == ["claude-sonnet-5"]

    def test_huggingface_uses_curated_default(self):
        assert list_models("huggingface") == ["openai/gpt-oss-120b:fastest"]

    def test_xai_uses_approved_list(self):
        assert list_models("xai") == ["grok-4.6"]

    def test_agnes_uses_approved_list(self):
        assert list_models("agnes") == ["agnes-2.5-flash"]

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
        s.model = "gpt-5.6-luna"
        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            build_chat_model(s)

    def test_openai_with_key_uses_chat_openai(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "OPENAI_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "openai"
        s.openai_api_key = "sk-test"
        s.model = "gpt-5.6-luna"
        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(s)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["model"] == "gpt-5.6-luna"
        assert kwargs["reasoning"] == {"effort": "medium"}
        assert kwargs["use_responses_api"] is True
        assert kwargs["max_completion_tokens"] == s.llm_max_tokens
        assert "temperature" not in kwargs

    def test_rejects_unapproved_openai_model(self):
        settings = Settings(_env_file=None)
        settings.provider = "openai"
        settings.model = "gpt-4o"
        settings.openai_api_key = "sk-test"
        with pytest.raises(LLMProviderError, match="gpt-5.6-luna"):
            build_chat_model(settings)

    def test_huggingface_without_key_raises(self):
        settings = Settings(
            _env_file=None,
            provider="huggingface",
            model="openai/gpt-oss-120b:fastest",
        )
        with pytest.raises(LLMProviderError, match="HF_TOKEN"):
            build_chat_model(settings)

    def test_huggingface_uses_direct_router(self):
        settings = Settings(
            _env_file=None,
            provider="huggingface",
            model="Qwen/Qwen3-Coder-480B-A35B-Instruct:fastest",
            hf_token="hf-test",
        )
        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(settings)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "hf-test"  # pragma: allowlist secret
        assert kwargs["base_url"] == "https://router.huggingface.co/v1"
        assert kwargs["reasoning"] == {"effort": "medium"}
        assert kwargs["use_responses_api"] is True

    def test_xai_uses_direct_api(self):
        settings = Settings(
            _env_file=None,
            provider="xai",
            model="grok-4.6",
            xai_api_key="xai-test",  # pragma: allowlist secret
        )
        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(settings)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "xai-test"  # pragma: allowlist secret
        assert kwargs["base_url"] == "https://api.x.ai/v1"
        assert kwargs["reasoning"] == {"effort": "medium"}
        assert kwargs["use_responses_api"] is True

    def test_agnes_without_key_raises(self):
        settings = Settings(
            _env_file=None,
            provider="agnes",
            model="agnes-2.5-flash",
        )
        with pytest.raises(LLMProviderError, match="AGNES_API_KEY"):
            build_chat_model(settings)

    def test_agnes_uses_documented_chat_thinking(self):
        settings = Settings(
            _env_file=None,
            provider="agnes",
            model="agnes-2.5-flash",
            agnes_api_key="agnes-test",  # pragma: allowlist secret
        )
        with patch("langchain_openai.ChatOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(settings)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "agnes-test"  # pragma: allowlist secret
        assert kwargs["base_url"] == "https://apihub.agnes-ai.com/v1"
        assert kwargs["model"] == "agnes-2.5-flash"
        assert kwargs["use_responses_api"] is False
        assert kwargs["extra_body"] == {
            "max_tokens": settings.llm_max_tokens,
            "chat_template_kwargs": {"enable_thinking": True},
        }
        assert "reasoning" not in kwargs

    def test_gemini_uses_medium_thinking_without_sampling(self):
        settings = Settings(
            _env_file=None,
            provider="gemini",
            model="gemini-3.7-flash",
            google_api_key="google-test",  # pragma: allowlist secret
        )
        with patch("langchain_google_genai.ChatGoogleGenerativeAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(settings)
        _, kwargs = mock_cls.call_args
        assert kwargs["thinking_level"] == "medium"
        assert "temperature" not in kwargs

    def test_anthropic_uses_medium_adaptive_thinking_without_sampling(self):
        settings = Settings(
            _env_file=None,
            provider="anthropic",
            model="claude-sonnet-5",
            anthropic_api_key="anthropic-test",  # pragma: allowlist secret
        )
        with patch("langchain_anthropic.ChatAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            build_chat_model(settings)
        _, kwargs = mock_cls.call_args
        assert kwargs["effort"] == "medium"
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert "temperature" not in kwargs

    def test_gemini_without_key_raises(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "GOOGLE_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "gemini"
        s.model = "gemini-3.7-flash"
        with pytest.raises(LLMProviderError, match="GOOGLE_API_KEY"):
            build_chat_model(s)

    def test_anthropic_without_key_raises(self, monkeypatch):
        for v in ("NL2SQL_PROVIDER", "ANTHROPIC_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        reset_settings_cache()
        s = get_settings()
        s.provider = "anthropic"
        s.model = "claude-sonnet-5"
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
