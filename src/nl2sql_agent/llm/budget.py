"""Persistent, fail-closed reservations for explicitly budgeted model runs.

Uncertain calls retain their reservation. This ledger never stores prompts,
credentials, endpoints, or provider response bodies.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class BudgetExhausted(RuntimeError):  # noqa: N818 - a terminal workflow outcome
    """A call cannot be made within the remaining budget."""


class Invokable(Protocol):
    """Minimal message-invocation interface for the agent and budget wrapper."""

    def invoke(self, messages: list[dict[str, str]], /) -> object:
        """Send message dictionaries and return a provider response object."""
        ...


@dataclass(frozen=True)
class Rates:
    """Finite nonnegative input/output prices in USD per million tokens."""

    input: Decimal
    output: Decimal

    def __post_init__(self) -> None:
        if any(not value.is_finite() or value < 0 for value in (self.input, self.output)):
            raise ValueError("Rates must be finite and nonnegative")

    def cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Return Decimal cost for token counts; negative counts raise ValueError."""
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token counts cannot be negative")
        return (self.input * input_tokens + self.output * output_tokens) / 1_000_000


class BudgetLedger:
    """Atomically reserve costs across processes sharing the same ledger file."""

    def __init__(self, path: Path, *, limit: Decimal = Decimal("2")) -> None:
        if not limit.is_finite() or limit <= 0:
            raise ValueError("Budget must be finite and positive")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.limit = limit
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS budget (id TEXT PRIMARY KEY, amount TEXT NOT NULL, status TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS budget_config (id INTEGER PRIMARY KEY CHECK(id=1), ceiling TEXT NOT NULL)"
            )
            conn.execute("INSERT OR IGNORE INTO budget_config VALUES (1, ?)", (str(limit),))
            stored = Decimal(
                conn.execute("SELECT ceiling FROM budget_config WHERE id=1").fetchone()[0]
            )
            if limit != stored:
                raise ValueError("Existing ledger ceiling cannot be changed")

    @property
    def committed(self) -> Decimal:
        """Return settled costs plus outstanding reservations in USD."""
        with sqlite3.connect(self.path) as conn:
            return self._total(conn)

    @staticmethod
    def _total(conn: sqlite3.Connection) -> Decimal:
        return sum(
            (Decimal(row[0]) for row in conn.execute("SELECT amount FROM budget")), Decimal(0)
        )

    def reserve(self, amount: Decimal) -> str:
        """Reserve a finite nonnegative amount and return its ID.

        Invalid amounts raise ValueError; insufficient capacity raises BudgetExhausted."""
        if not amount.is_finite() or amount < 0:
            raise ValueError("Reservation must be finite and nonnegative")
        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if self._total(conn) + amount > self.limit:
                raise BudgetExhausted("Model budget exhausted; no request sent")
            reservation = str(uuid4())
            conn.execute("INSERT INTO budget VALUES (?, ?, 'reserved')", (reservation, str(amount)))
        return reservation

    def reconcile(self, reservation: str, actual: Decimal) -> None:
        """Settle reservation with actual cost; invalid or settled IDs raise ValueError.

        An overrun is recorded before BudgetExhausted is raised."""
        if not actual.is_finite() or actual < 0:
            raise ValueError("Actual cost must be finite and nonnegative")
        with sqlite3.connect(self.path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT amount, status FROM budget WHERE id=?", (reservation,)
            ).fetchone()
            if row is None or row[1] != "reserved":
                raise ValueError("Unknown or already reconciled reservation")
            # Record even an unexpected overrun truthfully, then prevent more calls.
            conn.execute(
                "UPDATE budget SET amount=?, status='settled' WHERE id=?",
                (str(actual), reservation),
            )
        if actual > Decimal(row[0]):
            raise BudgetExhausted("Provider usage exceeded the conservative reservation")


class BudgetedModel:
    """Wrap invoke-only benchmark clients. Disable SDK retries on the client.

    Reserve a byte-per-token upper estimate plus message framing and the full
    output cap. Cache discounts are ignored conservatively. Missing usage or
    exceptions leave the reservation charged. Unknown pricing must be resolved
    before constructing this wrapper.
    """

    def __init__(
        self, model: Invokable, ledger: BudgetLedger, rates: Rates, *, max_tokens: int
    ) -> None:
        if max_tokens <= 0:
            raise ValueError("Output cap must be positive")
        self.model, self.ledger, self.rates, self.max_tokens = model, ledger, rates, max_tokens

    def invoke(self, messages: list[dict[str, str]]) -> object:
        """Reserve for messages, invoke once and reconcile validated usage only.

        Provider errors propagate and retain reservations. BudgetExhausted can occur
        before the call or after reported usage exceeds the reservation."""
        input_bound = (
            sum(len(message["content"].encode("utf-8")) + 256 for message in messages) + 1024
        )
        reservation = self.ledger.reserve(self.rates.cost(input_bound, self.max_tokens))
        response = self.model.invoke(messages)
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict) and all(
            type(usage.get(key)) is int and usage[key] >= 0
            for key in ("input_tokens", "output_tokens")
        ):
            self.ledger.reconcile(
                reservation, self.rates.cost(usage["input_tokens"], usage["output_tokens"])
            )
        return response
