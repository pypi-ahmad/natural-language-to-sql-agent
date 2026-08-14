"""Tests for the hosted-model pricing catalog."""

from __future__ import annotations

import pytest

from nl2sql_agent.llm.pricing import MODEL_PRICING, estimate_model_cost


def test_estimates_standard_model_cost_from_reported_tokens():
    assert estimate_model_cost("gpt-5.6-luna", 1_000_000, 500_000) == pytest.approx(0.8)


def test_catalog_contains_every_priced_hosted_model():
    assert {
        model: (pricing.input_price, pricing.output_price)
        for model, pricing in MODEL_PRICING.items()
    } == {
        "claude-sonnet-5": (2.00, 10.00),
        "gemini-3.7-flash": (0.75, 3.75),
        "gemini-3.5-flash-lite": (0.30, 2.50),
        "gpt-5.6-luna": (0.20, 1.20),
        "gpt-5.6-terra": (2.00, 12.00),
        "grok-4.6": (2.00, 6.00),
    }


def test_unpriced_model_has_no_cost_estimate():
    assert estimate_model_cost("openai/gpt-oss-120b:fastest", 1_000, 500) is None
