"""No-network proof of persistent budget enforcement."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from nl2sql_agent.llm.budget import BudgetedModel, BudgetExhausted, BudgetLedger, Rates


def test_reservations_survive_restart_and_enforce_ceiling(tmp_path):
    path = tmp_path / "budget.db"
    ledger = BudgetLedger(path)
    reservation = ledger.reserve(Decimal("1.9"))
    with pytest.raises(BudgetExhausted):
        BudgetLedger(path).reserve(Decimal(".2"))
    ledger.reconcile(reservation, Decimal(".01"))
    assert BudgetLedger(path).committed == Decimal(".01")
    with pytest.raises(ValueError, match="ceiling"):
        BudgetLedger(path, limit=Decimal("3"))


def test_failed_call_retains_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db")
    model = Mock()
    model.invoke.side_effect = RuntimeError("offline")
    wrapper = BudgetedModel(model, ledger, Rates(Decimal(1), Decimal(1)), max_tokens=100)
    with pytest.raises(RuntimeError):
        wrapper.invoke([{"role": "user", "content": "test"}])
    assert ledger.committed > 0


def test_usage_reconciles_and_exhaustion_prevents_call(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.db")
    model = Mock()
    model.invoke.return_value = SimpleNamespace(
        usage_metadata={"input_tokens": 10, "output_tokens": 2}
    )
    wrapper = BudgetedModel(model, ledger, Rates(Decimal(1), Decimal(1)), max_tokens=100)
    wrapper.invoke([{"role": "user", "content": "test"}])
    assert ledger.committed == Decimal(".000012")
    ledger.reserve(Decimal("1.999988"))
    with pytest.raises(BudgetExhausted):
        wrapper.invoke([{"role": "user", "content": "test"}])
    assert model.invoke.call_count == 1


@pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity"])
def test_invalid_money_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        Rates(Decimal(bad), Decimal(1))
    with pytest.raises(ValueError):
        BudgetLedger(tmp_path / "budget.db", limit=Decimal(bad))
