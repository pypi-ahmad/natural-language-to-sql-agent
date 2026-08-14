"""LLM provider factory.

This module is the single source of truth for building LangChain chat
models from a :class:`Settings` instance. It also exposes a small
``list_models`` helper that discovers local Ollama models and returns the
approved catalog for hosted providers.

Design notes:
- We use ``langchain_ollama.ChatOllama`` (not the deprecated community
  import) per the current LangChain docs.
- Failures during model listing are logged and surfaced as empty lists
  rather than exceptions, so a broken Ollama connection doesn't break
  the Streamlit sidebar.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from langchain_core.language_models import BaseChatModel

from ..config import (
    Provider,
    Settings,
    default_model_for,
    get_settings,
    supported_models_for,
    validate_model_for,
)
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
    resolved_provider = _normalize_provider(provider or cfg.provider)
    if model is None and provider is not None and resolved_provider != cfg.provider:
        model = default_model_for(resolved_provider)
    model = model or cfg.model
    try:
        model = validate_model_for(resolved_provider, model)
    except ValueError as exc:
        raise LLMProviderError(str(exc)) from exc
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
    if resolved_provider == "anthropic":
        return _build_anthropic(cfg, **common)
    if resolved_provider == "gemini":
        return _build_gemini(cfg, **common)
    if resolved_provider == "huggingface":
        return _build_huggingface(cfg, **common)
    if resolved_provider == "xai":
        return _build_xai(cfg, **common)

    raise LLMProviderError(f"Unsupported provider: {resolved_provider}")


def _normalize_provider(provider: str | Provider | None) -> Provider:
    """Type-narrow a runtime provider argument to a :data:`Provider` literal."""
    if provider is None:
        return get_settings().provider
    p = provider.lower() if isinstance(provider, str) else provider
    if p in ("ollama", "huggingface", "openai", "anthropic", "gemini", "xai"):
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
    return _build_openai_compatible(
        api_key=cfg.openai_api_key,
        model=str(common["model"]),
        max_tokens=int(common["max_tokens"]),
        timeout=float(common["timeout"]),
    )


def _build_gemini(cfg: Settings, **common: Any) -> ChatGoogleGenerativeAI:
    if not cfg.google_api_key:
        raise LLMProviderError("GOOGLE_API_KEY is required for provider=gemini")
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        api_key=cfg.google_api_key,
        model=common["model"],
        max_tokens=common["max_tokens"],
        request_timeout=common["timeout"],
        thinking_level="medium",
    )


def _build_anthropic(cfg: Settings, **common: Any) -> ChatAnthropic:
    if not cfg.anthropic_api_key:
        raise LLMProviderError("ANTHROPIC_API_KEY is required for provider=anthropic")
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(  # type: ignore[call-arg]
        api_key=cfg.anthropic_api_key,
        model_name=common["model"],
        max_tokens=common["max_tokens"],
        timeout=common["timeout"],
        thinking={"type": "adaptive"},
        effort="medium",
    )


def _build_huggingface(cfg: Settings, **common: Any) -> ChatOpenAI:
    if not cfg.hf_token:
        raise LLMProviderError("HF_TOKEN is required for provider=huggingface")
    return _build_openai_compatible(
        api_key=cfg.hf_token,
        model=str(common["model"]),
        max_tokens=int(common["max_tokens"]),
        timeout=float(common["timeout"]),
        base_url="https://router.huggingface.co/v1",
    )


def _build_xai(cfg: Settings, **common: Any) -> ChatOpenAI:
    if not cfg.xai_api_key:
        raise LLMProviderError("XAI_API_KEY is required for provider=xai")
    return _build_openai_compatible(
        api_key=cfg.xai_api_key,
        model=str(common["model"]),
        max_tokens=int(common["max_tokens"]),
        timeout=float(common["timeout"]),
        base_url="https://api.x.ai/v1",
    )


def _build_openai_compatible(
    *,
    api_key: str,
    model: str,
    max_tokens: int,
    timeout: float,
    base_url: str | None = None,
) -> ChatOpenAI:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_completion_tokens=max_tokens,
        timeout=timeout,
        reasoning={"effort": "medium"},
        use_responses_api=True,
    )


# ---- Model discovery --------------------------------------------------------


OLLAMA_FALLBACK_MODELS = supported_models_for("ollama")
HUGGINGFACE_FALLBACK_MODELS = supported_models_for("huggingface")
OPENAI_FALLBACK_MODELS = supported_models_for("openai")
ANTHROPIC_FALLBACK_MODELS = supported_models_for("anthropic")
GEMINI_FALLBACK_MODELS = supported_models_for("gemini")
XAI_FALLBACK_MODELS = supported_models_for("xai")


def fallback_models(provider: Provider) -> Iterable[str]:
    """Hard-coded fallback list when the SDK call fails or is unavailable."""
    return {
        "ollama": OLLAMA_FALLBACK_MODELS,
        "huggingface": HUGGINGFACE_FALLBACK_MODELS,
        "openai": OPENAI_FALLBACK_MODELS,
        "anthropic": ANTHROPIC_FALLBACK_MODELS,
        "gemini": GEMINI_FALLBACK_MODELS,
        "xai": XAI_FALLBACK_MODELS,
    }[provider]


def list_models(
    provider: Provider | str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> list[str]:
    """Discover available model IDs for ``provider``.

    Hosted providers return their approved choices without a network call.
    Ollama returns an empty list on connection errors.
    """
    resolved: Provider = _normalize_provider(provider)
    try:
        if resolved == "ollama":
            return _list_ollama(base_url or "http://localhost:11434")
        return list(fallback_models(resolved))
    except Exception as exc:
        logger.warning(
            "list_models failed for {provider} type={kind}",
            provider=resolved,
            kind=exc.__class__.__name__,
        )
    return []


def _list_ollama(base_url: str) -> list[str]:
    import ollama

    try:
        client = ollama.Client(host=base_url)
        try:
            info = client.list()
        finally:
            client.close()
    except Exception as exc:
        # Fall back to the sync ``ollama.list()`` which uses the default URL.
        logger.debug(
            "ollama.Client failed type={kind}; falling back to ollama.list()",
            kind=exc.__class__.__name__,
        )
        info = ollama.list()

    models: list[str] = []
    raw = getattr(info, "models", None) or info.get("models", [])
    for m in raw:
        name = getattr(m, "model", None) or m.get("name") or m.get("model")
        if name:
            models.append(name)
    return models
