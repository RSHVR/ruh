"""Run-level metrics + aggregation + significance testing.

Per-run output goes in ``RunMetrics``. The aggregation layer computes
``AggregatedMetric`` with mean / sample variance / CI built from the
t-distribution (``scipy.stats.t``), and ``paired_t_test`` returns the t,
two-sided p, Cohen's d (paired). ``holm_correction`` applies the
Holm-Bonferroni step-down so we can report family-wise-corrected p alongside
raw p values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# RunMetrics — what each (config, product, run) produces
# ---------------------------------------------------------------------------

@dataclass
class RunMetrics:
    config_name: str
    product_id: str
    run_idx: int
    model_id: str = ""

    # Cost
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    total_cost_usd: float = 0.0
    cache_hit_rate: Optional[float] = None
    search_count: int = 0
    search_cost_usd: float = 0.0

    # Latency
    total_latency_ms: float = 0.0
    per_phase_latency_ms: Dict[str, float] = field(default_factory=dict)
    tool_call_count: int = 0

    # Correctness vs ground truth (Tier A only — None when not in scope)
    allergen_tp: Optional[int] = None
    allergen_fp: Optional[int] = None
    allergen_fn: Optional[int] = None
    pfas_tp: Optional[int] = None
    pfas_fp: Optional[int] = None
    pfas_fn: Optional[int] = None
    harm_score: int = 0
    harm_score_in_expected_range: Optional[bool] = None

    # Divergence vs reference (Tier B only — None when not in scope)
    reference_jaccard_allergens: Optional[float] = None
    reference_jaccard_pfas: Optional[float] = None
    reference_harm_delta: Optional[int] = None

    # Judge
    judge_overall: Optional[float] = None
    judge_allergen_recall: Optional[float] = None
    judge_allergen_precision: Optional[float] = None
    judge_pfas_recall: Optional[float] = None
    judge_pfas_precision: Optional[float] = None
    judge_groundedness: Optional[float] = None
    judge_calibration: Optional[float] = None
    judge_hallucination_count: Optional[int] = None
    judge_disagreement: Optional[float] = None

    # Reliability
    failure_type: Optional[str] = None  # None on success
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

@dataclass
class AggregatedMetric:
    name: str
    n: int
    mean: float
    sample_variance: float
    stddev: float
    cv: float
    ci_low: float
    ci_high: float


def _t_critical(df: int, alpha: float = 0.05) -> float:
    """Two-sided t critical value for the given df, prefer scipy if available."""
    try:
        from scipy.stats import t
        return float(t.ppf(1 - alpha / 2, df))
    except ImportError:
        # Lookup table fallback for common df. Not exhaustive — degrade
        # gracefully to z=1.96 for df>=30 only if scipy is missing.
        if df >= 30:
            return 1.96
        # Approximate values for df 1..29 at 0.05 two-sided
        table = {
            1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
            6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
            11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
            16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
            21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
            26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
        }
        return table.get(df, 1.96)


def aggregate(values: Sequence[float], name: str = "metric") -> AggregatedMetric:
    """Mean + **sample** variance (n-1) + t-distribution 95% CI.

    Returns an AggregatedMetric. For n<2, variance/CV/CI are NaN.
    """
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n == 0:
        nan = float("nan")
        return AggregatedMetric(name, 0, nan, nan, nan, nan, nan, nan)
    mean = sum(vals) / n
    if n < 2:
        return AggregatedMetric(name, n, mean, float("nan"), float("nan"), float("nan"), mean, mean)
    sample_var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    stddev = math.sqrt(sample_var)
    cv = stddev / abs(mean) if mean != 0 else float("nan")
    se = stddev / math.sqrt(n)
    crit = _t_critical(n - 1)
    margin = crit * se
    return AggregatedMetric(
        name=name,
        n=n,
        mean=mean,
        sample_variance=sample_var,
        stddev=stddev,
        cv=cv,
        ci_low=mean - margin,
        ci_high=mean + margin,
    )


# ---------------------------------------------------------------------------
# Significance testing
# ---------------------------------------------------------------------------

@dataclass
class PairedTestResult:
    n: int
    mean_diff: float
    t_stat: float
    p_value: float
    cohens_d: float          # paired d = mean(diff) / stddev(diff)
    df: int


def paired_t_test(a: Sequence[float], b: Sequence[float]) -> PairedTestResult:
    """Two-sided paired t-test + paired Cohen's d.

    ``a`` and ``b`` must be the same length and paired by index (e.g. same
    product, same run index). Uses scipy when available, falls back to a
    self-contained implementation otherwise.
    """
    if len(a) != len(b):
        raise ValueError(f"paired_t_test: length mismatch {len(a)} vs {len(b)}")
    n = len(a)
    if n < 2:
        return PairedTestResult(n=n, mean_diff=float("nan"), t_stat=float("nan"),
                                p_value=float("nan"), cohens_d=float("nan"), df=max(0, n - 1))
    diffs = [float(x) - float(y) for x, y in zip(a, b)]
    mean_diff = sum(diffs) / n
    var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
    if var_diff == 0:
        # Perfect agreement: t and d are degenerate; treat as no detectable diff.
        return PairedTestResult(n=n, mean_diff=mean_diff, t_stat=0.0,
                                p_value=1.0, cohens_d=0.0, df=n - 1)
    sd_diff = math.sqrt(var_diff)
    se_diff = sd_diff / math.sqrt(n)
    t_stat = mean_diff / se_diff
    df = n - 1

    try:
        from scipy.stats import t as t_dist
        p = float(2 * (1 - t_dist.cdf(abs(t_stat), df)))
    except ImportError:
        # Approximation via the symmetric Student CDF (no scipy fallback).
        # We use the well-known series approximation. For our use case the
        # report's interpretability is "p < 0.05", and the fallback is fine.
        p = _student_t_sf_two_sided(abs(t_stat), df) * 2
        p = min(max(p, 0.0), 1.0)

    return PairedTestResult(
        n=n,
        mean_diff=mean_diff,
        t_stat=t_stat,
        p_value=p,
        cohens_d=mean_diff / sd_diff,
        df=df,
    )


def _student_t_sf_two_sided(t_abs: float, df: int) -> float:
    """Survival function for Student's t (lower tail). Fallback only."""
    # Abramowitz & Stegun 26.7.4 approximation
    x = df / (df + t_abs * t_abs)
    a = 0.5 * df
    b = 0.5
    return 0.5 * _betainc(a, b, x)


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function via continued fraction. Best-effort."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1 - x)
    )
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 1e-10) -> float:
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h


def holm_correction(p_values: Sequence[float]) -> List[float]:
    """Holm-Bonferroni step-down correction.

    Returns a list of corrected p-values in the **same order** as the input.
    Family-wise alpha control: a test is significant at alpha=A iff its
    corrected p < A.
    """
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    corrected_in_sorted: List[float] = []
    prev = 0.0
    for rank, (_, p) in enumerate(indexed):
        adj = (n - rank) * p
        adj = max(prev, min(1.0, adj))  # monotonic, clamp to [prev, 1]
        corrected_in_sorted.append(adj)
        prev = adj
    out = [0.0] * n
    for sorted_rank, (orig_idx, _) in enumerate(indexed):
        out[orig_idx] = corrected_in_sorted[sorted_rank]
    return out


# ---------------------------------------------------------------------------
# Set comparisons (Jaccard) used for divergence and TP/FP/FN
# ---------------------------------------------------------------------------

def jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    sa = {x.strip().lower() for x in a if x}
    sb = {x.strip().lower() for x in b if x}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def confusion(detected: Sequence[str], expected: Sequence[str]) -> Tuple[int, int, int]:
    sd = {x.strip().lower() for x in detected if x}
    se = {x.strip().lower() for x in expected if x}
    tp = len(sd & se)
    fp = len(sd - se)
    fn = len(se - sd)
    return tp, fp, fn


__all__ = [
    "RunMetrics",
    "AggregatedMetric",
    "PairedTestResult",
    "aggregate",
    "paired_t_test",
    "holm_correction",
    "jaccard",
    "confusion",
]
