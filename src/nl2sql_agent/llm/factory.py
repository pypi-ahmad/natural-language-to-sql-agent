"""LLM provider factory.

This module is the single source of truth for building LangChain chat
models from a :class:`Settings` instance. It also exposes a small
``list_models`` helper that queries the underlying SDK to enumerate
available models per provider.

Design notes:
- We use ``langchain_ollama.ChatOllama`` (not the deprecated community
  import) per the current LangChain docs.
- We keep native SDK imports optional so the package can be used without
  installing every provider's SDK. ``list_models`` returns ``[]`` when
  the SDK is not installed.
- Failures during model listing are logged and surfaced as empty lists
  rather than exceptions, so a broken Ollama connection doesn't break
  the Streamlit sidebar.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel

from ..config import Provider, Settings, get_settings
from ..utils import get_logger

if TYPE_CHECKING:
    from langchain_anthropic import ChatAnthropic
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI

logger = get_logger(__name__)


class LLMProviderError(RuntimeError):
    """Raised when the LLM provider cannot be initialized."""


def build_chat_model(
    settings: Settings | None = None,
    *,
    provider: Provider | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """Build a LangChain chat model from runtime configuration.

    Args:
        settings: A :class:`Settings` instance. Defaults to the cached one.
        provider: Override the provider from ``settings``.
        model: Override the model from ``settings``.
        temperature: Override the temperature from ``settings``.
        max_tokens: Override the max_tokens from ``settings``.

    Returns:
        A configured :class:`BaseChatModel` instance.

    Raises:
        LLMProviderError: If the provider is unknown or required credentials
            are missing.
    """
    cfg = settings or get_settings()
    resolved_provider: Provider = _normalize_provider(provider)
    model = model or cfg.model
    temperature = cfg.llm_temperature if temperature is None else temperature
    max_tokens = cfg.llm_max_tokens if max_tokens is None else max_tokens

    common: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": cfg.llm_request_timeout_seconds,
    }

    if resolved_provider == "ollama":
        return _build_ollama(cfg, **common)
    if resolved_provider == "openai":
        return _build_openai(cfg, **common)
    if resolved_provider == "gemini":
        return _build_gemini(cfg, **common)
    if resolved_provider == "anthropic":
        return _build_anthropic(cfg, **common)

    raise LLMProviderError(f"Unsupported provider: {resolved_provider}")


def _normalize_provider(provider: str | Provider | None) -> Provider:
    """Type-narrow a runtime provider argument to a :data:`Provider` literal."""
    if provider is None:
        return get_settings().provider
    p = provider.lower() if isinstance(provider, str) else provider
    if p in ("ollama", "openai", "gemini", "anthropic"):
        return p  # type: ignore[return-value]
    raise LLMProviderError(f"Unsupported provider: {provider}")


def _build_ollama(cfg: Settings, **common: Any) -> ChatOllama:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=common["model"],
        base_url=cfg.ollama_base_url,
        temperature=common["temperature"],
        num_predict=common["max_tokens"],
        timeout=common["timeout"],
    )


def _build_openai(cfg: Settings, **common: Any) -> ChatOpenAI:
    if not cfg.openai_api_key:
        raise LLMProviderError("OPENAI_API_KEY is required for provider=openai")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=cfg.openai_api_key,
        model=common["model"],
        temperature=common["temperature"],
        max_tokens=common["max_tokens"],
        timeout=common["timeout"],
    )


def _build_gemini(cfg: Settings, **common: Any) -> ChatGoogleGenerativeAI:
    if not cfg.google_api_key:
        raise LLMProviderError("GOOGLE_API_KEY is required for provider=gemini")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        google_api_key=cfg.google_api_key,
        model=common["model"],
        temperature=common["temperature"],
        max_output_tokens=common["max_tokens"],
        timeout=common["timeout"],
    )


def _build_anthropic(cfg: Settings, **common: Any) -> ChatAnthropic:
    if not cfg.anthropic_api_key:
        raise LLMProviderError("ANTHROPIC_API_KEY is required for provider=anthropic")
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(  # type: ignore[call-arg]
        api_key=cfg.anthropic_api_key,
        model_name=common["model"],
        temperature=common["temperature"],
        max_tokens=common["max_tokens"],
        timeout=common["timeout"],
    )


# ---- Model discovery --------------------------------------------------------


# Curated fallback for providers that don't expose a public list-models endpoint.
ANTHROPIC_FALLBACK_MODELS: tuple[str, ...] = (
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-opus-latest",
    "claude-3-7-sonnet-latest",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
)

OPENAI_FALLBACK_MODELS: tuple[str, ...] = (
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "o1",
    "o1-mini",
)

GEMINI_FALLBACK_MODELS: tuple[str, ...] = (
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.0-pro",
)

OLLAMA_FALLBACK_MODELS: tuple[str, ...] = (
    "phi4-mini:3.8b",
    "qwen3.5:4b",
    "qwen3.5:2b",
    "llama3.1",
    "mistral",
)


def fallback_models(provider: Provider) -> Iterable[str]:
    """Hard-coded fallback list when the SDK call fails or is unavailable."""
    return {
        "ollama": OLLAMA_FALLBACK_MODELS,
        "openai": OPENAI_FALLBACK_MODELS,
        "gemini": GEMINI_FALLBACK_MODELS,
        "anthropic": ANTHROPIC_FALLBACK_MODELS,
    }[provider]


def list_models(
    provider: Provider | str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> list[str]:
    """Discover available model IDs for ``provider``.

    Returns an empty list on any error. Never raises. Use
    :func:`fallback_models` if the list comes back empty.
    """
    resolved: Provider = _normalize_provider(provider)
    try:
        if resolved == "ollama":
            return _list_ollama(base_url or "http://localhost:11434")
        if resolved == "openai":
            return _list_openai(api_key)
        if resolved == "gemini":
            return _list_gemini(api_key)
        if resolved == "anthropic":
            return list(ANTHROPIC_FALLBACK_MODELS)
    except Exception as exc:
        logger.warning("list_models failed for {provider}: {err}", provider=resolved, err=exc)
    return []


def _list_ollama(base_url: str) -> list[str]:
    import ollama

    try:
        client = ollama.Client(host=base_url)
        info = client.list()
    except Exception as exc:
        # Fall back to the sync ``ollama.list()`` which uses the default URL.
        logger.debug("ollama.Client failed ({err}); falling back to ollama.list()", err=exc)
        info = ollama.list()

    models: list[str] = []
    raw = getattr(info, "models", None) or info.get("models", [])
    for m in raw:
        name = getattr(m, "model", None) or m.get("name") or m.get("model")
        if name:
            models.append(name)
    return models


def _list_openai(api_key: str | None) -> list[str]:
    if not api_key:
        return []
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    ids = sorted(
        (m.id for m in client.models.list() if "gpt" in m.id or m.id.startswith("o")),
        reverse=True,
    )
    return list(ids)


def _list_gemini(api_key: str | None) -> list[str]:
    if not api_key:
        return []
    from google import genai

    client = genai.Client(api_key=api_key)
    out: list[str] = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if not actions or "generateContent" in actions:
            name = m.name or ""
            out.append(name.replace("models/", "", 1))
    return out
