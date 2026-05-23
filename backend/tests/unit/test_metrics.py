"""Statistics in metrics.py — Holm-Bonferroni, paired t-test, Cohen's d."""

import math
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.benchmark.metrics import (  # noqa: E402
    aggregate,
    confusion,
    holm_correction,
    jaccard,
    paired_t_test,
)


def test_holm_correction_known_table():
    # Holm step-down: sort ascending, multiply by (n - rank).
    # p = [0.01, 0.02, 0.03, 0.04, 0.05], n=5
    # sorted same; corrected = max(5*.01, 4*.02, 3*.03, 2*.04, 1*.05) monotonized
    # = .05, .08, .09, .08, .05 → monotonized: .05, .08, .09, .09, .09
    raw = [0.01, 0.02, 0.03, 0.04, 0.05]
    corrected = holm_correction(raw)
    expected = [0.05, 0.08, 0.09, 0.09, 0.09]
    for a, b in zip(corrected, expected):
        assert abs(a - b) < 1e-9, f"expected {expected}, got {corrected}"


def test_holm_preserves_input_order():
    # If we shuffle, the corrected p-values should still align with their
    # original positions.
    raw = [0.05, 0.01, 0.04, 0.02, 0.03]
    corrected = holm_correction(raw)
    # The smallest raw was 0.01 at index 1 — its corrected should also be smallest.
    smallest_idx = corrected.index(min(corrected))
    assert smallest_idx == 1


def test_holm_clamps_to_one():
    # For high raw p-values the Holm step-down multiplier pushes corrected
    # values past 1.0; we clamp to [0, 1].
    assert holm_correction([0.9, 0.9, 0.9]) == [1.0, 1.0, 1.0]
    assert all(p <= 1.0 for p in holm_correction([0.6, 0.7, 0.8, 0.9]))


def test_holm_empty_input():
    assert holm_correction([]) == []


def test_paired_t_perfect_agreement():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = paired_t_test(a, a)
    assert result.mean_diff == 0.0
    assert result.cohens_d == 0.0
    assert result.p_value == 1.0


def test_paired_t_zero_variance_is_degenerate():
    """When every pair differs by the same constant, paired-diff variance
    is zero — we treat this as "no detectable difference relative to its
    own noise" rather than infinite t. The cleaner test for power is
    test_paired_t_with_real_variation below."""
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [3.0, 4.0, 5.0, 6.0, 7.0]  # diffs are all exactly -2
    result = paired_t_test(a, b)
    assert result.mean_diff == -2.0
    assert result.t_stat == 0.0
    assert result.p_value == 1.0
    assert result.cohens_d == 0.0


def test_paired_t_with_real_variation():
    a = [10.0, 12.0, 9.0, 11.0, 13.0, 10.5, 11.5, 9.5]
    b = [11.0, 13.0, 10.0, 12.5, 14.0, 11.5, 12.0, 10.5]
    result = paired_t_test(a, b)
    # b is consistently higher → mean_diff negative.
    assert result.mean_diff < 0
    assert result.p_value < 0.05
    assert abs(result.cohens_d) > 0.5  # at least a medium effect


def test_aggregate_uses_sample_variance():
    """Sample variance divides by n-1, not n. For [1, 3] mean=2, n-1=1, var=2."""
    agg = aggregate([1.0, 3.0])
    assert agg.mean == 2.0
    assert abs(agg.sample_variance - 2.0) < 1e-12


def test_aggregate_n_lt_2_returns_nan_variance():
    agg = aggregate([5.0])
    assert agg.mean == 5.0
    assert math.isnan(agg.sample_variance)


def test_aggregate_uses_t_distribution_for_small_n():
    # 5 observations → t critical at 4 df ≈ 2.776 (not z=1.96)
    agg = aggregate([10.0, 11.0, 9.0, 12.0, 8.0])
    assert agg.n == 5
    # CI half-width = t * stddev / sqrt(n). With stddev=sqrt(2.5)≈1.581 and
    # se≈0.707, t_4=2.776 → margin ≈1.963. So 10 ± 1.96.
    assert 7.9 < agg.ci_low < 8.1
    assert 11.9 < agg.ci_high < 12.1


def test_jaccard_basics():
    assert jaccard([], []) == 1.0
    assert jaccard(["a"], []) == 0.0
    assert jaccard(["a", "b"], ["b", "c"]) == 1 / 3
    # Case-insensitive
    assert jaccard(["FOO"], ["foo"]) == 1.0


def test_confusion_basics():
    tp, fp, fn = confusion(["a", "b", "c"], ["b", "c", "d"])
    assert (tp, fp, fn) == (2, 1, 1)
