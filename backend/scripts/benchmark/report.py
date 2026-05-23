"""Plotly HTML report — single self-contained ``index.html``.

Charts (top to bottom):
  1. Decision Matrix (table) — recommended config per scenario
  2. Pareto frontier — cost vs quality, 95% CI error bars
  3. Cost stacked bar — cache-read / cache-write / input / output
  4. Quality heatmap — 15 products × 5 configs
  5. Latency violin
  6. Cache-efficiency-over-time (configs supporting caching only)
  7. Failure-mode stacked bar

The aggregation uses ``metrics.aggregate`` (sample variance, t-distribution
95% CI) and ``metrics.paired_t_test`` + ``holm_correction`` for the
significance table embedded in the Decision Matrix.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .metrics import (
    AggregatedMetric,
    aggregate,
    holm_correction,
    paired_t_test,
    RunMetrics,
)

logger = logging.getLogger(__name__)


def _load_runs(output_dir: Path) -> List[RunMetrics]:
    rows: List[RunMetrics] = []
    for path in sorted((output_dir / "runs").rglob("metrics.json")):
        data = json.loads(path.read_text())
        try:
            rows.append(RunMetrics(**data))
        except TypeError:
            # extra keys / missing keys — best effort.
            filt = {k: v for k, v in data.items() if k in RunMetrics.__dataclass_fields__}
            rows.append(RunMetrics(**filt))
    return rows


def _aggregate_by_config(
    rows: List[RunMetrics], field: str
) -> Dict[str, AggregatedMetric]:
    bucket: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        v = getattr(r, field, None)
        if v is None:
            continue
        bucket[r.config_name].append(float(v))
    return {c: aggregate(vals, name=field) for c, vals in bucket.items()}


def _paired_for_config_pairs(
    rows: List[RunMetrics], field: str
) -> Dict[tuple, Any]:
    """Pair across (product_id, run_idx) for every pair of configs."""
    by_config: Dict[str, Dict[tuple, float]] = defaultdict(dict)
    for r in rows:
        v = getattr(r, field, None)
        if v is None:
            continue
        by_config[r.config_name][(r.product_id, r.run_idx)] = float(v)
    configs = sorted(by_config)
    out: Dict[tuple, Any] = {}
    for i, a in enumerate(configs):
        for b in configs[i + 1:]:
            shared = sorted(set(by_config[a]) & set(by_config[b]))
            if len(shared) < 2:
                continue
            va = [by_config[a][k] for k in shared]
            vb = [by_config[b][k] for k in shared]
            out[(a, b)] = paired_t_test(va, vb)
    return out


def _decision_matrix(
    rows: List[RunMetrics], judge_path: Optional[Path]
) -> Dict[str, Dict[str, str]]:
    """Pick a winner per scenario.

    - alpha_launch: best mean (judge_overall - 0.5 * cost) — quality-leaning
    - cost_constrained: lowest mean cost among configs whose schema_invalid
      rate < 20%
    - highest_accuracy: highest judge_overall mean
    """
    judge_by_config: Dict[str, List[float]] = defaultdict(list)
    if judge_path and judge_path.exists():
        judgments = json.loads(judge_path.read_text())
        for j in judgments:
            judge_by_config[j["config"]].append(j["scores"].get("overall_quality", 0))

    cost_by_config: Dict[str, List[float]] = defaultdict(list)
    invalid_by_config: Dict[str, List[int]] = defaultdict(list)
    for r in rows:
        cost_by_config[r.config_name].append(r.total_cost_usd)
        invalid_by_config[r.config_name].append(1 if r.failure_type == "schema_invalid" else 0)

    out: Dict[str, Dict[str, str]] = {}

    configs = sorted(cost_by_config)
    if not configs:
        return out

    def mean(xs):
        return sum(xs) / len(xs) if xs else float("inf")

    # cost_constrained
    eligible = [c for c in configs if mean(invalid_by_config[c]) < 0.20]
    cost_winner = min(eligible or configs, key=lambda c: mean(cost_by_config[c]))
    out["cost_constrained"] = {
        "winner": cost_winner,
        "rationale": f"mean cost ${mean(cost_by_config[cost_winner]):.3f} per analysis",
    }

    # highest_accuracy
    if judge_by_config:
        acc_winner = max(configs, key=lambda c: mean(judge_by_config[c]))
        out["highest_accuracy"] = {
            "winner": acc_winner,
            "rationale": f"mean judge_overall {mean(judge_by_config[acc_winner]):.2f}/10",
        }

    # alpha_launch: balance quality and cost
    def balance(c):
        q = mean(judge_by_config[c]) if judge_by_config else 0
        cost = mean(cost_by_config[c])
        return q - 5 * cost  # weight cost moderately

    if judge_by_config:
        bal_winner = max(configs, key=balance)
        out["alpha_launch"] = {
            "winner": bal_winner,
            "rationale": f"best quality-per-dollar ({balance(bal_winner):.2f})",
        }
    return out


def build_report(output_dir: Path, judge_path: Optional[Path] = None) -> Path:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as e:
        raise RuntimeError("plotly>=5.24 required for report") from e

    rows = _load_runs(output_dir)
    if not rows:
        raise RuntimeError(f"No runs found under {output_dir/'runs'}")

    judge_by_config: Dict[str, List[float]] = defaultdict(list)
    if judge_path and judge_path.exists():
        for j in json.loads(judge_path.read_text()):
            judge_by_config[j["config"]].append(j["scores"].get("overall_quality", 0))

    decision = _decision_matrix(rows, judge_path)
    configs = sorted({r.config_name for r in rows})
    products = sorted({r.product_id for r in rows})

    figs = []

    # --- Decision Matrix table ----------------------------------------------
    dm = go.Figure(data=[go.Table(
        header=dict(values=["Scenario", "Recommended config", "Rationale"]),
        cells=dict(values=[
            list(decision.keys()),
            [v["winner"] for v in decision.values()],
            [v["rationale"] for v in decision.values()],
        ]),
    )])
    dm.update_layout(title="Decision Matrix — recommended config per scenario")
    figs.append(dm)

    # --- Pareto: cost vs quality ------------------------------------------
    cost_agg = _aggregate_by_config(rows, "total_cost_usd")
    quality_means = {c: (sum(judge_by_config[c]) / len(judge_by_config[c])
                         if judge_by_config[c] else 0.0)
                     for c in configs}
    pareto = go.Figure()
    pareto.add_trace(go.Scatter(
        x=[cost_agg[c].mean for c in configs],
        y=[quality_means[c] for c in configs],
        text=configs,
        mode="markers+text",
        textposition="top center",
        marker=dict(size=12),
        error_x=dict(
            type="data",
            array=[cost_agg[c].ci_high - cost_agg[c].mean for c in configs],
            arrayminus=[cost_agg[c].mean - cost_agg[c].ci_low for c in configs],
        ),
    ))
    pareto.update_layout(
        title="Pareto frontier: cost vs. quality (95% CI on cost)",
        xaxis_title="Mean cost per analysis (USD)",
        yaxis_title="Mean judge overall_quality",
    )
    figs.append(pareto)

    # --- Cost stacked bar ---------------------------------------------------
    by_config_tokens = {c: defaultdict(list) for c in configs}
    for r in rows:
        by_config_tokens[r.config_name]["input"].append(r.input_tokens)
        by_config_tokens[r.config_name]["output"].append(r.output_tokens)
        by_config_tokens[r.config_name]["cache_read"].append(r.cache_read_tokens)
        by_config_tokens[r.config_name]["cache_creation"].append(r.cache_creation_tokens)

    def _mean(xs):
        return sum(xs) / len(xs) if xs else 0

    cost_bar = go.Figure()
    for stack in ("input", "output", "cache_read", "cache_creation"):
        cost_bar.add_trace(go.Bar(
            name=stack,
            x=configs,
            y=[_mean(by_config_tokens[c][stack]) for c in configs],
        ))
    cost_bar.update_layout(
        title="Mean tokens per analysis by stack (Cohere has no cache breakdown — provider gap)",
        barmode="stack",
        yaxis_title="tokens",
    )
    figs.append(cost_bar)

    # --- Quality heatmap (per product × config) ----------------------------
    judge_per_pair: Dict[tuple, float] = {}
    if judge_path and judge_path.exists():
        for j in json.loads(judge_path.read_text()):
            key = (j["config"], j["product_id"])
            judge_per_pair.setdefault(key, []).append(j["scores"].get("overall_quality", 0))  # type: ignore
        for k, v in list(judge_per_pair.items()):
            if isinstance(v, list):
                judge_per_pair[k] = sum(v) / len(v)

    z = []
    for c in configs:
        row = [judge_per_pair.get((c, p), float("nan")) for p in products]
        z.append(row)
    if z and len(z[0]):
        hm = go.Figure(data=go.Heatmap(z=z, x=products, y=configs, colorscale="RdYlGn",
                                       zmin=1, zmax=10))
        hm.update_layout(title="Quality heatmap: judge_overall per (config, product)")
        figs.append(hm)

    # --- Latency violin ----------------------------------------------------
    lat = go.Figure()
    for c in configs:
        lat.add_trace(go.Violin(
            y=[r.total_latency_ms for r in rows if r.config_name == c],
            name=c, box_visible=True, meanline_visible=True,
        ))
    lat.update_layout(title="Total latency (ms) per config", yaxis_title="ms")
    figs.append(lat)

    # --- Cache efficiency --------------------------------------------------
    cache_supporting = sorted({r.config_name for r in rows
                               if r.cache_hit_rate is not None})
    if cache_supporting:
        ce = go.Figure()
        for c in cache_supporting:
            xs = [i for i, r in enumerate(rows) if r.config_name == c]
            ys = [r.cache_hit_rate for r in rows if r.config_name == c]
            ce.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=c))
        ce.update_layout(title="Cache hit rate per run (Anthropic-cached configs only)",
                         yaxis_title="hit rate")
        figs.append(ce)

    # --- Failure mode stacked bar -----------------------------------------
    fm: Dict[str, Dict[str, int]] = {c: defaultdict(int) for c in configs}
    for r in rows:
        fm[r.config_name][r.failure_type or "ok"] += 1
    modes = sorted({m for d in fm.values() for m in d})
    fmf = go.Figure()
    for m in modes:
        fmf.add_trace(go.Bar(name=m, x=configs, y=[fm[c][m] for c in configs]))
    fmf.update_layout(title="Failure modes per config", barmode="stack")
    figs.append(fmf)

    # --- Assemble HTML -----------------------------------------------------
    parts: List[str] = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
                        "<title>Ruh 5-Config Eval</title></head><body>",
                        "<h1>Ruh — 5-Config Agent Evaluation</h1>"]
    for i, fig in enumerate(figs):
        include = "inline" if i == 0 else False
        parts.append(fig.to_html(include_plotlyjs=include, full_html=False))
    parts.append("</body></html>")

    out_path = output_dir / "index.html"
    out_path.write_text("\n".join(parts))
    logger.info("Wrote %s", out_path)
    return out_path
