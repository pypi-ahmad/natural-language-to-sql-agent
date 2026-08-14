"""LLM module: provider factory, model discovery, chat-model construction."""

from .factory import (
    ANTHROPIC_FALLBACK_MODELS,
    GEMINI_FALLBACK_MODELS,
    HUGGINGFACE_FALLBACK_MODELS,
    OLLAMA_FALLBACK_MODELS,
    OPENAI_FALLBACK_MODELS,
    XAI_FALLBACK_MODELS,
    LLMProviderError,
    build_chat_model,
    fallback_models,
    list_models,
)
from .pricing import MODEL_PRICING, ModelPricing, estimate_model_cost

__all__ = [
    "ANTHROPIC_FALLBACK_MODELS",
    "GEMINI_FALLBACK_MODELS",
    "HUGGINGFACE_FALLBACK_MODELS",
    "MODEL_PRICING",
    "OLLAMA_FALLBACK_MODELS",
    "OPENAI_FALLBACK_MODELS",
    "XAI_FALLBACK_MODELS",
    "LLMProviderError",
    "ModelPricing",
    "build_chat_model",
    "estimate_model_cost",
    "fallback_models",
    "list_models",
]
