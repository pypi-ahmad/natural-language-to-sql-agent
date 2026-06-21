"""LLM module: provider factory, model discovery, chat-model construction."""

from .factory import (
    ANTHROPIC_FALLBACK_MODELS,
    GEMINI_FALLBACK_MODELS,
    OLLAMA_FALLBACK_MODELS,
    OPENAI_FALLBACK_MODELS,
    LLMProviderError,
    build_chat_model,
    fallback_models,
    list_models,
)

__all__ = [
    "ANTHROPIC_FALLBACK_MODELS",
    "GEMINI_FALLBACK_MODELS",
    "OLLAMA_FALLBACK_MODELS",
    "OPENAI_FALLBACK_MODELS",
    "LLMProviderError",
    "build_chat_model",
    "fallback_models",
    "list_models",
]
