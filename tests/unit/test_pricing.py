"""Tests for the hosted-model pricing catalog."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from nl2sql_agent.llm.pricing import (
    DEFAULT_PRICING_RULES,
    MODEL_PRICING,
    UsageRecord,
    calculate_cost,
    effective_pricing_rule,
    estimate_model_cost,
)


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


def _rule(model: str):
    return next(rule for rule in DEFAULT_PRICING_RULES if rule.model == model)


def test_cache_read_tokens_use_cache_rate():
    result = calculate_cost(
        _rule("gpt-5.6-luna"),
        [UsageRecord("writer", 1_000_000, 0, cache_read_tokens=500_000)],
    )
    assert result.total_cost == Decimal("0.110000000000")


def test_batch_and_fast_rates_require_actual_request_mode():
    batch = calculate_cost(
        _rule("claude-sonnet-5"),
        [UsageRecord("writer", 1_000_000, 1_000_000, request_mode="batch")],
    )
    fast = calculate_cost(
        _rule("grok-4.6"),
        [UsageRecord("writer", 1_000_000, 1_000_000, request_mode="fast")],
    )
    assert batch.total_cost == Decimal("6.000000000000")
    assert fast.total_cost == Decimal("16.000000000000")


def test_long_context_is_applied_per_call_not_aggregate():
    result = calculate_cost(
        _rule("gpt-5.6-terra"),
        [
            UsageRecord("writer", 200_000, 0),
            UsageRecord("summarizer", 200_000, 0),
        ],
    )
    assert result.total_cost == Decimal("0.800000000000")
    assert not any(line.long_context for line in result.lines)


def test_long_context_threshold_is_strictly_greater_than():
    result = calculate_cost(
        _rule("grok-4.6"),
        [UsageRecord("writer", 200_001, 1)],
    )
    assert result.lines[0].long_context is True
    assert result.lines[0].input_rate == Decimal("4.00")


def test_effective_window_end_is_exclusive():
    rules = list(DEFAULT_PRICING_RULES)
    assert (
        effective_pricing_rule(
            rules,
            "gemini-3.7-flash",
            datetime(2026, 12, 31, 23, 59, tzinfo=UTC),
        )
        is not None
    )
    assert (
        effective_pricing_rule(
            rules,
            "gemini-3.7-flash",
            datetime(2027, 1, 1, tzinfo=UTC),
        )
        is None
    )
