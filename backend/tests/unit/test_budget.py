"""BudgetTracker — cap overflow + pre-flight refusal."""

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.benchmark.budget import BudgetExceeded, BudgetTracker  # noqa: E402


def test_add_under_cap_succeeds():
    bt = BudgetTracker(max_cost_usd=10.0)
    bt.add(3.0)
    bt.add(4.0)
    assert bt.spent_usd == 7.0
    assert bt.remaining() == 3.0


def test_add_exact_cap_succeeds():
    bt = BudgetTracker(max_cost_usd=10.0)
    bt.add(10.0)
    assert bt.spent_usd == 10.0


def test_add_overflow_raises():
    bt = BudgetTracker(max_cost_usd=10.0)
    bt.add(8.0)
    with pytest.raises(BudgetExceeded):
        bt.add(3.0)
    # Spend should not have changed after the failed add.
    assert bt.spent_usd == 8.0


def test_add_negative_raises_value_error():
    bt = BudgetTracker(max_cost_usd=10.0)
    with pytest.raises(ValueError):
        bt.add(-1.0)


def test_warn_at_threshold_fires_once(caplog):
    bt = BudgetTracker(max_cost_usd=10.0, warn_at=0.5)
    import logging
    with caplog.at_level(logging.WARNING):
        bt.add(6.0)
        bt.add(1.0)
    warn_records = [r for r in caplog.records if r.levelname == "WARNING"]
    # We should see exactly one budget-warning line.
    assert any("Budget at" in r.getMessage() for r in warn_records)
    n_budget_warns = sum(1 for r in warn_records if "Budget at" in r.getMessage())
    assert n_budget_warns == 1


def test_preflight_refuses_when_estimate_exceeds_cap():
    with pytest.raises(BudgetExceeded):
        BudgetTracker.preflight(
            estimated_total_cost=80.0,
            max_cost_usd=80.0,
            margin=1.4,
            force=False,
        )


def test_preflight_allows_with_force():
    # Should NOT raise even though projected > cap.
    BudgetTracker.preflight(
        estimated_total_cost=80.0,
        max_cost_usd=50.0,
        margin=1.4,
        force=True,
    )


def test_preflight_passes_under_cap():
    BudgetTracker.preflight(
        estimated_total_cost=50.0,
        max_cost_usd=80.0,
        margin=1.4,
        force=False,
    )
