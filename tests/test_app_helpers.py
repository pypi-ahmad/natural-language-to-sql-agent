"""
Tests for app.py helper functions: get_available_models, get_llm_instance.
Target: app.py lines 19-90.

These functions live in app.py which has extensive module-level Streamlit calls.
We mock the 'streamlit' module before importing to prevent runtime context errors.

Coverage intent:
- get_available_models: Anthropic returns hardcoded list (lines 57-61)
- get_available_models: no api_key returns [] for cloud providers (lines 41, 47)
- get_available_models: unknown provider returns None (Bug M-03)
- get_available_models: Ollama path with mocked SDK
- get_available_models: exception handling returns []
- get_llm_instance: unknown provider returns None (Bug M-02)
- get_llm_instance: Ollama returns ChatOllama instance
"""
import sys
import os
import importlib
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="module")
def app_module(tmp_path_factory):
    """
    Import app.py with streamlit mocked to prevent UI context errors.
    Uses a temp directory to isolate the company.db side effect from module-level code.

    Scope=module means app.py is imported ONCE for all tests in this file.
    """
    tmp_dir = tmp_path_factory.mktemp("app_test")
    prev_cwd = os.getcwd()
    os.chdir(str(tmp_dir))

    # Mock streamlit — all st.* calls become no-ops
    mock_st = MagicMock()
    prev_st = sys.modules.get("streamlit")
    sys.modules["streamlit"] = mock_st

    # Force fresh import of app module
    sys.modules.pop("app", None)

    try:
        import app as app_mod
        yield app_mod
    finally:
        os.chdir(prev_cwd)
        sys.modules.pop("app", None)
        if prev_st is not None:
            sys.modules["streamlit"] = prev_st
        else:
            sys.modules.pop("streamlit", None)


# =============================================================================
# get_available_models() tests
# =============================================================================
class TestGetAvailableModelsAnthropic:
    """Anthropic returns a hardcoded list (app.py:57-61)."""

    def test_returns_three_models(self, app_module):
        result = app_module.get_available_models("Anthropic", "any-key")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_contains_sonnet(self, app_module):
        result = app_module.get_available_models("Anthropic", "key")
        assert "claude-3-5-sonnet-latest" in result

    def test_contains_haiku(self, app_module):
        result = app_module.get_available_models("Anthropic", "key")
        assert "claude-3-5-haiku-latest" in result

    def test_contains_opus(self, app_module):
        result = app_module.get_available_models("Anthropic", "key")
        assert "claude-3-opus-latest" in result

    def test_no_key_still_returns_list(self, app_module):
        """Anthropic path has no api_key guard — returns list even with None key."""
        result = app_module.get_available_models("Anthropic", None)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_empty_key_still_returns_list(self, app_module):
        result = app_module.get_available_models("Anthropic", "")
        assert len(result) == 3


class TestGetAvailableModelsNoKey:
    """Cloud providers require api_key — return [] when missing."""

    def test_openai_none_key(self, app_module):
        """app.py:41 — if not api_key: return []."""
        result = app_module.get_available_models("OpenAI", None)
        assert result == []

    def test_openai_empty_key(self, app_module):
        result = app_module.get_available_models("OpenAI", "")
        assert result == []

    def test_gemini_none_key(self, app_module):
        """app.py:47 — if not api_key: return []."""
        result = app_module.get_available_models("Gemini", None)
        assert result == []

    def test_gemini_empty_key(self, app_module):
        result = app_module.get_available_models("Gemini", "")
        assert result == []


class TestGetAvailableModelsUnknownProvider:
    """
    FIX VERIFICATION (Phase 2: M-03 — now fixed):
    Unknown provider now returns [] instead of None.
    """

    def test_unknown_provider_returns_empty_list(self, app_module):
        result = app_module.get_available_models("UnknownProvider", "key")
        assert result == []

    def test_empty_provider_returns_empty_list(self, app_module):
        result = app_module.get_available_models("", "key")
        assert result == []


class TestGetAvailableModelsOllama:
    """Test Ollama provider path with mocked SDK (app.py:33-37)."""

    def test_ollama_list_objects_format(self, app_module):
        """app.py:35-36 — handles model objects with .model attribute."""
        mock_model_1 = MagicMock()
        mock_model_1.model = "llama3:latest"
        mock_model_2 = MagicMock()
        mock_model_2.model = "mistral:latest"
        mock_response = MagicMock()
        mock_response.models = [mock_model_1, mock_model_2]

        with patch.object(app_module.ollama, "list", return_value=mock_response):
            result = app_module.get_available_models("Ollama")
            assert result == ["llama3:latest", "mistral:latest"]

    def test_ollama_list_dicts_format(self, app_module):
        """app.py:37 — handles dict format with 'name' key."""
        mock_response = {"models": [{"name": "llama3"}, {"name": "codellama"}]}

        with patch.object(app_module.ollama, "list", return_value=mock_response):
            result = app_module.get_available_models("Ollama")
            assert result == ["llama3", "codellama"]

    def test_ollama_exception_returns_empty_list(self, app_module):
        """app.py:63-64 — exception caught, returns []."""
        with patch.object(app_module.ollama, "list", side_effect=ConnectionError("no server")):
            result = app_module.get_available_models("Ollama")
            assert result == []


# =============================================================================
# get_llm_instance() tests
# =============================================================================
class TestGetLlmInstanceUnknownProvider:
    """
    FIX VERIFICATION (Phase 2: M-02 — now fixed):
    Unknown provider now raises ValueError instead of returning None.
    """

    def test_unknown_raises_value_error(self, app_module):
        with pytest.raises(ValueError, match="Unsupported provider"):
            app_module.get_llm_instance("UnknownProvider", "model", "key")

    def test_empty_provider_raises_value_error(self, app_module):
        with pytest.raises(ValueError, match="Unsupported provider"):
            app_module.get_llm_instance("", "model", "key")


class TestGetLlmInstanceOllama:
    """Test Ollama LLM instantiation (app.py:79-81)."""

    def test_ollama_returns_chat_ollama(self, app_module):
        """app.py:80-81 — imports ChatOllama and returns instance."""
        with patch("langchain_community.chat_models.ChatOllama") as MockChatOllama:
            mock_instance = MagicMock()
            MockChatOllama.return_value = mock_instance
            result = app_module.get_llm_instance("Ollama", "llama3")
            assert result is mock_instance
            MockChatOllama.assert_called_once_with(model="llama3")
