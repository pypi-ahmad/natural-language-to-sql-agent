"""Versioned model pricing and exact per-call cost estimates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

RequestMode = Literal["standard", "batch", "fast"]
MILLION = Decimal(1_000_000)
SEED_EFFECTIVE_AT = datetime(2026, 8, 14, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Backward-compatible standard API prices in USD per million tokens."""

    display_name: str
    input_price: float
    output_price: float
    details: str


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """Provider-reported usage for one actual model call."""

    stage: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    request_mode: RequestMode = "standard"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PricingRule:
    """One non-overlapping effective pricing window for a model."""

    rule_id: str
    model: str
    display_name: str
    effective_from: datetime
    effective_to: datetime | None
    standard_input: Decimal
    standard_output: Decimal
    cache_read_input: Decimal | None = None
    cache_creation_input: Decimal | None = None
    batch_input: Decimal | None = None
    batch_output: Decimal | None = None
    fast_input: Decimal | None = None
    fast_output: Decimal | None = None
    long_context_threshold: int | None = None
    long_context_input: Decimal | None = None
    long_context_output: Decimal | None = None
    notes: str = ""

    def is_effective(self, at: datetime) -> bool:
        """Return whether ``at`` falls inside this UTC effective window."""
        instant = at.astimezone(UTC)
        return self.effective_from <= instant and (
            self.effective_to is None or instant < self.effective_to
        )


@dataclass(frozen=True, slots=True)
class CostLine:
    """Calculated cost for one usage record."""

    stage: str
    request_mode: RequestMode
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    input_rate: Decimal
    output_rate: Decimal
    cache_read_rate: Decimal
    cache_creation_rate: Decimal
    long_context: bool
    cost: Decimal


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Immutable cost calculation stored with a run."""

    model: str
    pricing_rule_id: str
    calculated_at: datetime
    lines: tuple[CostLine, ...]
    total_cost: Decimal

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["calculated_at"] = self.calculated_at.isoformat()
        data["total_cost"] = str(self.total_cost)
        for line in data["lines"]:
            for key in (
                "input_rate",
                "output_rate",
                "cache_read_rate",
                "cache_creation_rate",
                "cost",
            ):
                line[key] = str(line[key])
        return data


class PricingUnavailableError(ValueError):
    """Raised when an actual usage mode has no configured price."""


def _d(value: str) -> Decimal:
    return Decimal(value)


DEFAULT_PRICING_RULES: tuple[PricingRule, ...] = (
    PricingRule(
        "claude-sonnet-5-20260814",
        "claude-sonnet-5",
        "Sonnet 5",
        SEED_EFFECTIVE_AT,
        None,
        _d("2.00"),
        _d("10.00"),
        batch_input=_d("1.00"),
        batch_output=_d("5.00"),
        notes="Standard pricing; Batch API is 50% lower.",
    ),
    PricingRule(
        "gemini-3.7-flash-20260814",
        "gemini-3.7-flash",
        "Gemini Flash 3.7",
        SEED_EFFECTIVE_AT,
        datetime(2027, 1, 1, tzinfo=UTC),
        _d("0.75"),
        _d("3.75"),
        notes="Promotional rate through December 31, 2026.",
    ),
    PricingRule(
        "gemini-3.5-flash-lite-20260814",
        "gemini-3.5-flash-lite",
        "Gemini 3.5 Flash Lite",
        SEED_EFFECTIVE_AT,
        None,
        _d("0.30"),
        _d("2.50"),
        batch_input=_d("0.15"),
        batch_output=_d("1.25"),
        notes="Lowest-cost Gemini Flash tier.",
    ),
    PricingRule(
        "gpt-5.6-luna-20260814",
        "gpt-5.6-luna",
        "GPT-5.6 Luna",
        SEED_EFFECTIVE_AT,
        None,
        _d("0.20"),
        _d("1.20"),
        cache_read_input=_d("0.02"),
        notes="Prompt cache reads cost $0.02 per million tokens.",
    ),
    PricingRule(
        "gpt-5.6-terra-20260814",
        "gpt-5.6-terra",
        "GPT-5.6 Terra",
        SEED_EFFECTIVE_AT,
        None,
        _d("2.00"),
        _d("12.00"),
        long_context_threshold=272_000,
        long_context_input=_d("4.00"),
        long_context_output=_d("24.00"),
        notes="Rates double above 272k input tokens per call.",
    ),
    PricingRule(
        "grok-4.6-20260814",
        "grok-4.6",
        "Grok 4.6",
        SEED_EFFECTIVE_AT,
        None,
        _d("2.00"),
        _d("6.00"),
        fast_input=_d("4.00"),
        fast_output=_d("12.00"),
        long_context_threshold=200_000,
        long_context_input=_d("4.00"),
        long_context_output=_d("12.00"),
        notes="Fast mode or prompts above 200k tokens use $4/$12 rates.",
    ),
)


MODEL_PRICING: dict[str, ModelPricing] = {
    rule.model: ModelPricing(
        rule.display_name,
        float(rule.standard_input),
        float(rule.standard_output),
        rule.notes,
    )
    for rule in DEFAULT_PRICING_RULES
}


def effective_pricing_rule(
    rules: tuple[PricingRule, ...] | list[PricingRule],
    model: str,
    at: datetime | None = None,
) -> PricingRule | None:
    """Return the single effective rule for ``model`` at ``at``."""
    instant = (at or datetime.now(UTC)).astimezone(UTC)
    matches = [rule for rule in rules if rule.model == model and rule.is_effective(instant)]
    if len(matches) > 1:
        raise ValueError(f"Overlapping pricing rules for {model}")
    return matches[0] if matches else None


def _mode_rates(rule: PricingRule, mode: RequestMode) -> tuple[Decimal, Decimal]:
    if mode == "standard":
        return rule.standard_input, rule.standard_output
    if mode == "batch" and rule.batch_input is not None and rule.batch_output is not None:
        return rule.batch_input, rule.batch_output
    if mode == "fast" and rule.fast_input is not None and rule.fast_output is not None:
        return rule.fast_input, rule.fast_output
    raise PricingUnavailableError(f"No {mode} pricing is configured for {rule.model}")


def calculate_cost(
    rule: PricingRule,
    usage_records: list[UsageRecord] | tuple[UsageRecord, ...],
    *,
    calculated_at: datetime | None = None,
) -> CostBreakdown:
    """Calculate exact estimated cost from actual per-call usage."""
    lines: list[CostLine] = []
    total = Decimal(0)
    for usage in usage_records:
        input_tokens = max(int(usage.input_tokens), 0)
        output_tokens = max(int(usage.output_tokens), 0)
        cache_read = min(max(int(usage.cache_read_tokens), 0), input_tokens)
        cache_creation = min(max(int(usage.cache_creation_tokens), 0), input_tokens - cache_read)
        input_rate, output_rate = _mode_rates(rule, usage.request_mode)
        long_context = bool(
            rule.long_context_threshold is not None and input_tokens > rule.long_context_threshold
        )
        if long_context:
            if rule.long_context_input is None or rule.long_context_output is None:
                raise PricingUnavailableError(
                    f"No long-context pricing is configured for {rule.model}"
                )
            input_rate = rule.long_context_input
            output_rate = rule.long_context_output
        cache_rate = rule.cache_read_input if rule.cache_read_input is not None else input_rate
        cache_creation_rate = (
            rule.cache_creation_input if rule.cache_creation_input is not None else input_rate
        )
        cost = (
            Decimal(input_tokens - cache_read - cache_creation) * input_rate
            + Decimal(cache_read) * cache_rate
            + Decimal(cache_creation) * cache_creation_rate
            + Decimal(output_tokens) * output_rate
        ) / MILLION
        cost = cost.quantize(Decimal("0.000000000001"))
        total += cost
        lines.append(
            CostLine(
                stage=usage.stage,
                request_mode=usage.request_mode,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_creation_tokens=cache_creation,
                input_rate=input_rate,
                output_rate=output_rate,
                cache_read_rate=cache_rate,
                cache_creation_rate=cache_creation_rate,
                long_context=long_context,
                cost=cost,
            )
        )
    return CostBreakdown(
        model=rule.model,
        pricing_rule_id=rule.rule_id,
        calculated_at=(calculated_at or datetime.now(UTC)).astimezone(UTC),
        lines=tuple(lines),
        total_cost=total.quantize(Decimal("0.000000000001")),
    )


def estimate_model_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate standard cost using the built-in compatibility catalog."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    return (
        max(input_tokens, 0) * pricing.input_price + max(output_tokens, 0) * pricing.output_price
    ) / 1_000_000
