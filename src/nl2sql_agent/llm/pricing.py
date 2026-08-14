"""Hosted-model prices used for per-run UI cost estimates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Standard API prices in USD per one million tokens."""

    display_name: str
    input_price: float
    output_price: float
    details: str


MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-5": ModelPricing(
        "Sonnet 5",
        2.00,
        10.00,
        "Standard pricing; the Batch API receives a 50% discount.",
    ),
    "gemini-3.7-flash": ModelPricing(
        "Gemini Flash 3.7",
        0.75,
        3.75,
        "Promotional rate through December 31, 2026.",
    ),
    "gemini-3.5-flash-lite": ModelPricing(
        "Gemini 3.5 Flash Lite",
        0.30,
        2.50,
        "Batch processing costs $0.15 input and $1.25 output per 1M tokens.",
    ),
    "gpt-5.6-luna": ModelPricing(
        "GPT-5.6 Luna",
        0.20,
        1.20,
        "Prompt cache reads cost $0.02 per 1M tokens.",
    ),
    "gpt-5.6-terra": ModelPricing(
        "GPT-5.6 Terra",
        2.00,
        12.00,
        "Long-context prompts above 272k input tokens use doubled rates.",
    ),
    "grok-4.6": ModelPricing(
        "Grok 4.6",
        2.00,
        6.00,
        "Fast mode or prompts above 200k tokens cost $4 input and $12 output per 1M.",
    ),
}


def estimate_model_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate standard API cost from provider-reported token counts."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    return (
        max(input_tokens, 0) * pricing.input_price + max(output_tokens, 0) * pricing.output_price
    ) / 1_000_000
